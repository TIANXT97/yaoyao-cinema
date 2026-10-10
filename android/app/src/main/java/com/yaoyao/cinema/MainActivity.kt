package com.yaoyao.cinema

import android.os.Bundle
import android.webkit.WebSettings
import com.getcapacitor.BridgeActivity
import com.yaoyao.cinema.plugins.NativePlayerPlugin

/**
 * 夭夭影社 · 安卓宿主 Activity。
 *
 * 对齐 docs/ARCHITECTURE.md 4.1：
 * - 继承 Capacitor [BridgeActivity]，承载 Vue SPA 与原生桥接
 * - 注册本地原生硬解播放插件 [NativePlayerPlugin]（必须在 super.onCreate 之前）
 * - WebView 显式允许混合内容：页面 http scheme 与 NAS 明文 http 直连（局域网场景）
 */
class MainActivity : BridgeActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        // 注册本地插件：WebView 侧 registerPlugin('NativePlayer') 方能命中
        registerPlugin(NativePlayerPlugin::class.java)
        super.onCreate(savedInstanceState)
        bridge.webView.settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
    }
}
