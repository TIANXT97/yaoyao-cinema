package com.yaoyao.cinema

import android.app.Activity
import android.content.Intent
import android.content.pm.ActivityInfo
import android.net.Uri
import android.os.Bundle
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView

/**
 * PlayerActivity · Media3 (ExoPlayer) 原生硬解播放。
 *
 * 对齐 docs/ARCHITECTURE.md 4.2.3：
 * - 全屏沉浸 + 横屏锁定
 * - 默认 MediaCodec 硬件解码优先
 * - HTTP Range 数据源直连 NAS，零转码原画直出
 * - 退出时回传 position / duration / completed
 */
@UnstableApi
class PlayerActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_POSITION = "position"
        const val EXTRA_TITLE = "title"

        const val EXTRA_RESULT_POSITION = "position"
        const val EXTRA_RESULT_DURATION = "duration"
        const val EXTRA_RESULT_COMPLETED = "completed"

        private const val USER_AGENT = "YaoyaoCinema/1.0"
        private const val COMPLETION_THRESHOLD = 0.9

        /** 允许直连播放的 URI scheme 白名单。 */
        private val PLAYABLE_SCHEMES = setOf(
            "http", "https", "rtsp", "rtmp", "content", "file", "asset", "android.resource",
        )
    }

    private var player: ExoPlayer? = null
    private lateinit var playerView: PlayerView
    private lateinit var gestureDetector: GestureDetector
    private var resultSent = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 全屏沉浸：内容延伸至系统栏，支持手势临时唤出
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

        setContentView(R.layout.activity_player)
        playerView = findViewById(R.id.player_view)

        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent): Boolean = true

            override fun onDoubleTap(e: MotionEvent): Boolean {
                val exo = player ?: return false
                if (e.x < playerView.width / 2f) exo.seekBack() else exo.seekForward()
                return true
            }

            override fun onScroll(
                e1: MotionEvent?,
                e2: MotionEvent,
                distanceX: Float,
                distanceY: Float,
            ): Boolean {
                val exo = player ?: return false
                if (kotlin.math.abs(distanceX) <= kotlin.math.abs(distanceY)) return false
                val width = playerView.width.takeIf { it > 0 } ?: return false
                val duration = exo.duration.takeIf { it > 0L } ?: return false
                val delta = (-distanceX / width * duration).toLong()
                val target = (exo.currentPosition + delta).coerceIn(0L, duration)
                exo.seekTo(target)
                return true
            }
        })
        playerView.setOnTouchListener { _, event ->
            gestureDetector.onTouchEvent(event)
            false
        }

        val url = intent.getStringExtra(EXTRA_URL)
        if (url.isNullOrBlank() || !isPlayableUrl(url)) {
            Toast.makeText(this, R.string.player_invalid_url, Toast.LENGTH_SHORT).show()
            setResult(Activity.RESULT_CANCELED)
            finish()
            return
        }
        val startPosition = intent.getLongExtra(EXTRA_POSITION, 0L)
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty()

        // HTTP Range 数据源：直连 NAS 拉取原始字节
        val dataSourceFactory = DefaultHttpDataSource.Factory()
            .setUserAgent(USER_AGENT)
            .setAllowCrossProtocolRedirects(true)
            .setConnectTimeoutMs(15_000)
            .setReadTimeoutMs(20_000)

        val exoPlayer = ExoPlayer.Builder(this)
            .setMediaSourceFactory(DefaultMediaSourceFactory(dataSourceFactory))
            .setSeekBackIncrementMs(10_000)
            .setSeekForwardIncrementMs(10_000)
            .build()

        player = exoPlayer
        playerView.player = exoPlayer
        playerView.keepScreenOn = true
        playerView.setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)

        exoPlayer.setHandleAudioBecomingNoisy(true)
        exoPlayer.setMediaItem(
            MediaItem.Builder()
                .setUri(Uri.parse(url))
                .setMediaId(title.ifBlank { "yaoyao" })
                .build(),
        )
        if (startPosition > 0L) {
            exoPlayer.seekTo(startPosition)
        }
        exoPlayer.playWhenReady = true
        exoPlayer.prepare()
    }

    override fun onStop() {
        super.onStop()
        // 退到后台即暂停，避免后台占用解码器
        player?.pause()
    }

    override fun onPause() {
        super.onPause()
        // 极端场景（分屏销毁 / 系统强杀）下 onStop / finish 可能不执行，
        // 若 Activity 正在结束则兜底回传进度，防止续播点丢失。
        if (isFinishing) {
            sendResult()
        }
    }

    override fun finish() {
        // 必须在 super.finish() 之前回传：ActivityResult 需在销毁前 setResult，
        // 否则 WebView 侧的 play() Promise 会永久挂起（结果丢失）
        sendResult()
        super.finish()
    }

    override fun onDestroy() {
        sendResult()
        player?.release()
        player = null
        super.onDestroy()
    }

    /** 校验 URL 是否为可直连播放的合法地址（scheme 白名单 + 可解析）。 */
    private fun isPlayableUrl(url: String): Boolean {
        val uri = runCatching { Uri.parse(url) }.getOrNull() ?: return false
        val scheme = uri.scheme?.lowercase() ?: return false
        if (scheme !in PLAYABLE_SCHEMES) return false
        return when (scheme) {
            "http", "https", "rtsp", "rtmp" -> !uri.host.isNullOrBlank()
            else -> true
        }
    }

    /** 回传播放进度给 WebView（幂等）。 */
    private fun sendResult() {
        if (resultSent) return
        resultSent = true

        val exo = player
        if (exo == null) {
            setResult(Activity.RESULT_CANCELED)
            return
        }

        val duration = exo.duration.coerceAtLeast(0L)
        val position = exo.currentPosition.coerceAtLeast(0L)
        val completed =
            duration > 0L && position >= (duration * COMPLETION_THRESHOLD).toLong()

        val data = Intent().apply {
            putExtra(EXTRA_RESULT_POSITION, position)
            putExtra(EXTRA_RESULT_DURATION, duration)
            putExtra(EXTRA_RESULT_COMPLETED, completed)
        }
        setResult(Activity.RESULT_OK, data)
    }
}
