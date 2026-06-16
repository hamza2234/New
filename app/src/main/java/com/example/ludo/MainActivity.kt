package com.example.ludo

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            NativeLudoTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    LudoScreen()
                }
            }
        }
    }
}

@Composable
fun NativeLudoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF7851A9),
            secondary = Color(0xFFFF9F1C),
            tertiary = Color(0xFF2EC4B6),
            background = Color(0xFFFFF8F1),
            surface = Color(0xFFFFFFFF),
            onPrimary = Color.White,
            onSecondary = Color(0xFF2D1600),
            onTertiary = Color(0xFF001F1B),
        ),
        content = content,
    )
}

@Preview(showBackground = true, widthDp = 420)
@Composable
private fun LudoScreenPreview() {
    NativeLudoTheme {
        LudoScreen()
    }
}
