package com.yaoyao.cinema

import android.app.Activity
import android.content.Intent
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.view.WindowManager
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
    }

    private var player: ExoPlayer? = null
    private lateinit var playerView: PlayerView
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

        val url = intent.getStringExtra(EXTRA_URL)
        if (url.isNullOrBlank()) {
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
                .setUri(url)
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

    override fun onDestroy() {
        sendResult()
        player?.release()
        player = null
        super.onDestroy()
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
