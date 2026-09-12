package com.yaoyao.cinema.plugins

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import com.yaoyao.cinema.PlayerActivity
import com.yaoyao.cinema.R

/**
 * NativePlayerPlugin · 原生硬解播放桥接。
 *
 * 对齐 docs/ARCHITECTURE.md 4.2.2：
 * - 入参：url（绝对地址）/ position（续播毫秒）/ title
 * - 出参：position / duration / completed，取消时返回 { cancelled: true }
 *
 * WebView 侧调用：
 * ```
 * const NativePlayer = registerPlugin('NativePlayer')
 * await NativePlayer.play({ url, position, title })
 * ```
 */
@CapacitorPlugin(name = "NativePlayer")
class NativePlayerPlugin : Plugin() {

    @PluginMethod
    fun play(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank() || !isPlayableUrl(url)) {
            activity?.runOnUiThread {
                Toast.makeText(activity, R.string.player_invalid_url, Toast.LENGTH_SHORT).show()
            }
            call.reject("视频地址无效")
            return
        }

        val position: Long = call.getLong("position", 0L) ?: 0L
        val title: String = call.getString("title", "") ?: ""

        val intent = Intent(activity, PlayerActivity::class.java).apply {
            putExtra(PlayerActivity.EXTRA_URL, url)
            putExtra(PlayerActivity.EXTRA_POSITION, position)
            putExtra(PlayerActivity.EXTRA_TITLE, title)
        }

        // 以 Activity 结果回传播放进度
        startActivityForResult(call, intent, "handlePlayResult")
    }

    /** 校验 URL 是否为可直连播放的合法地址（scheme 白名单 + 可解析）。 */
    private fun isPlayableUrl(url: String): Boolean {
        val uri = runCatching { Uri.parse(url) }.getOrNull() ?: return false
        val scheme = uri.scheme?.lowercase() ?: return false
        return when (scheme) {
            "http", "https", "rtsp", "rtmp" -> !uri.host.isNullOrBlank()
            "content", "file", "asset", "android.resource" -> true
            else -> false
        }
    }

    @ActivityCallback
    private fun handlePlayResult(call: PluginCall?, result: ActivityResult) {
        if (call == null) return

        if (result.resultCode == Activity.RESULT_OK) {
            val data: Intent? = result.data
            val payload = JSObject().apply {
                put(
                    "position",
                    data?.getLongExtra(PlayerActivity.EXTRA_RESULT_POSITION, 0L) ?: 0L,
                )
                put(
                    "duration",
                    data?.getLongExtra(PlayerActivity.EXTRA_RESULT_DURATION, 0L) ?: 0L,
                )
                put(
                    "completed",
                    data?.getBooleanExtra(PlayerActivity.EXTRA_RESULT_COMPLETED, false)
                        ?: false,
                )
            }
            call.resolve(payload)
        } else {
            call.resolve(JSObject().put("cancelled", true))
        }
    }
}
