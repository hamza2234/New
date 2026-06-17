# Native Ludo Compose Screen

This repository now contains a native Android/Kotlin sample that can be copied into an existing social Android app and connected later to Firebase or any multiplayer backend.

## What is included

- Kotlin + Jetpack Compose + Material 3 Android app.
- `LudoScreen` with:
  - 15x15 Ludo board drawn with `Canvas`.
  - Four player colors and four pieces per player.
  - Smooth animated piece movement using Compose animation APIs.
  - Dice actions, turn handling, captures, safe cells, finish lane, and winner detection.
  - Solo mode with simple local bot turns.
  - Four-player local mode.
- Pure Kotlin game state and rules in `LudoGameEngine`, ready to be synced later with Firebase.

## Key files

```text
app/src/main/java/com/example/ludo/MainActivity.kt
app/src/main/java/com/example/ludo/LudoScreen.kt
app/src/main/java/com/example/ludo/LudoModels.kt
app/src/main/java/com/example/ludo/LudoGameEngine.kt
app/src/test/java/com/example/ludo/LudoGameEngineTest.kt
```

## Integration notes

To move the screen into your existing Android app:

1. Copy `LudoScreen.kt`, `LudoModels.kt`, and `LudoGameEngine.kt` into your app package.
2. Rename the package from `com.example.ludo` to your real package.
3. Add `LudoScreen()` as a destination in your existing navigation graph or open it from your social app's games entry point.
4. Replace the local `LudoGameEngine` calls with a ViewModel/repository that writes these actions to Firebase:
   - roll dice
   - move selected piece
   - reset match
   - join/leave multiplayer room

The UI receives a single `LudoUiState`, so a future Firebase implementation can keep the same screen and only change the state source.

## Build

The project is configured for:

- Android Gradle Plugin `9.2.0`
- Kotlin `2.3.21`
- Compose BOM `2026.05.00`
- compile/target SDK `37`

On a machine with Android SDK and Gradle available:

```bash
./gradlew test
./gradlew assembleDebug
```
