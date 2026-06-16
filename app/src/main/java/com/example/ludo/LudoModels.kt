package com.example.ludo

enum class LudoGameMode(val label: String) {
    Solo("فردي ضد الكمبيوتر"),
    FourPlayers("٤ لاعبين"),
}

enum class LudoPlayerColor(
    val label: String,
    val startCell: Int,
    val argb: Long,
) {
    Red("الأحمر", startCell = 0, argb = 0xFFE84855),
    Green("الأخضر", startCell = 13, argb = 0xFF2A9D8F),
    Yellow("الأصفر", startCell = 26, argb = 0xFFFFBE0B),
    Blue("الأزرق", startCell = 39, argb = 0xFF3A86FF),
}

data class LudoPlayer(
    val color: LudoPlayerColor,
    val isBot: Boolean,
)

data class LudoPiece(
    val id: Int,
    val owner: LudoPlayerColor,
    val progress: Int,
) {
    val isAtHome: Boolean = progress == HOME_PROGRESS
    val isFinished: Boolean = progress == FINISHED_PROGRESS
}

data class LudoMove(
    val pieceId: Int,
    val fromProgress: Int,
    val toProgress: Int,
    val capturedPieceIds: List<Int>,
)

data class LudoUiState(
    val gameMode: LudoGameMode,
    val players: List<LudoPlayer>,
    val pieces: List<LudoPiece>,
    val currentTurn: LudoPlayerColor,
    val diceValue: Int? = null,
    val canRoll: Boolean = true,
    val availablePieceIds: Set<Int> = emptySet(),
    val lastMove: LudoMove? = null,
    val winner: LudoPlayerColor? = null,
    val statusMessage: String = "ابدأ اللعبة وارم النرد",
) {
    val currentPlayer: LudoPlayer
        get() = players.first { it.color == currentTurn }
}

const val HOME_PROGRESS = -1
const val FIRST_TRACK_PROGRESS = 0
const val LAST_TRACK_PROGRESS = 51
const val FIRST_HOME_LANE_PROGRESS = 52
const val FINISHED_PROGRESS = 57
const val PIECES_PER_PLAYER = 4
