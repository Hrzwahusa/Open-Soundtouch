package com.opensoundtouch

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

/**
 * Intercepts the hardware volume keys **system-wide** (even in the background or
 * on the lock screen) while audio streaming is active, and forwards them to the
 * speaker / group instead of changing the phone volume.
 *
 * Only active while [AudioCaptureService.isRunning] — otherwise the keys pass
 * through untouched. The user must enable this service once under
 * Settings → Accessibility.
 */
class VolumeKeyAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (!AudioCaptureService.isRunning) return false
        val isVolumeKey = event.keyCode == KeyEvent.KEYCODE_VOLUME_UP ||
            event.keyCode == KeyEvent.KEYCODE_VOLUME_DOWN
        if (!isVolumeKey) return false

        // Consume both down and up so the system volume UI does not appear.
        if (event.action == KeyEvent.ACTION_DOWN) {
            val delta = if (event.keyCode == KeyEvent.KEYCODE_VOLUME_UP) 5 else -5
            AudioCaptureService.adjustVolume(delta)
        }
        return true
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}
}