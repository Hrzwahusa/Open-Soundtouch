package com.opensoundtouch.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// "Midnight" palette – same as the desktop app_theme.py
private val Accent = Color(0xFFF5A623)
private val Bg = Color(0xFF15171C)
private val Surface = Color(0xFF1E2129)
private val OnBg = Color(0xFFE7E9EE)
private val OnAccent = Color(0xFF17130A)

private val MidnightColors = darkColorScheme(
    primary = Accent,
    onPrimary = OnAccent,
    secondary = Accent,
    onSecondary = OnAccent,
    background = Bg,
    onBackground = OnBg,
    surface = Surface,
    onSurface = OnBg,
    surfaceVariant = Color(0xFF262A33),
    onSurfaceVariant = Color(0xFF8A909C),
)

@Composable
fun OpenSoundTouchTheme(content: @Composable () -> Unit) {
    // Always dark – the app has a single, intentional design.
    MaterialTheme(colorScheme = MidnightColors, content = content)
}