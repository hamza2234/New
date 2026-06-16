package com.example.ludo

import kotlin.random.Random

class LudoGameEngine(
    private val random: Random = Random.Default,
) {
    private var rollsSinceSix = 0

    fun newGame(mode: LudoGameMode): LudoUiState {
        rollsSinceSix = 0
        val players = LudoPlayerColor.entries.mapIndexed { index, color ->
            LudoPlayer(
                color = color,
                isBot = mode == LudoGameMode.Solo && index != 0,
            )
        }
        val pieces = players.flatMapIndexed { playerIndex, player ->
            List(PIECES_PER_PLAYER) { pieceIndex ->
                LudoPiece(
                    id = playerIndex * PIECES_PER_PLAYER + pieceIndex,
                    owner = player.color,
                    progress = HOME_PROGRESS,
                )
            }
        }

        return LudoUiState(
            gameMode = mode,
            players = players,
            pieces = pieces,
            currentTurn = players.first().color,
        )
    }

    fun rollDice(state: LudoUiState, forcedValue: Int? = null): LudoUiState {
        if (!state.canRoll || state.winner != null) return state

        val dice = forcedValue?.coerceIn(1, 6) ?: nextFairDice()
        val availableMoves = movablePieceIds(state, state.currentTurn, dice)

        return if (availableMoves.isEmpty()) {
            state.copy(
                diceValue = dice,
                canRoll = false,
                availablePieceIds = emptySet(),
                statusMessage = "النرد $dice ولا توجد حركة متاحة. انتظر انتهاء الوقت",
            )
        } else {
            state.copy(
                diceValue = dice,
                canRoll = false,
                availablePieceIds = availableMoves,
                statusMessage = "النرد $dice. اختر قطعة ${state.currentTurn.label} للتحريك",
            )
        }
    }

    fun movePiece(state: LudoUiState, pieceId: Int): LudoUiState {
        val dice = state.diceValue ?: return state
        if (state.canRoll || pieceId !in state.availablePieceIds || state.winner != null) return state

        val piece = state.pieces.firstOrNull { it.id == pieceId } ?: return state
        if (piece.owner != state.currentTurn) return state

        val targetProgress = targetProgress(piece.progress, dice) ?: return state
        val captureIds = capturedPieceIds(state, piece, targetProgress)
        val movedPieces = state.pieces.map { currentPiece ->
            when {
                currentPiece.id == piece.id -> currentPiece.copy(progress = targetProgress)
                currentPiece.id in captureIds -> currentPiece.copy(progress = HOME_PROGRESS)
                else -> currentPiece
            }
        }

        val winner = if (movedPieces
                .filter { it.owner == piece.owner }
                .all { it.progress == FINISHED_PROGRESS }
        ) {
            piece.owner
        } else {
            null
        }
        val nextTurn = if (winner == null && dice == 6) piece.owner else nextTurnAfter(state, dice)
        val captureText = if (captureIds.isNotEmpty()) " وتم التقاط ${captureIds.size} قطعة" else ""
        val status = when {
            winner != null -> "فاز ${winner.label} باللعبة"
            dice == 6 -> "حركة ممتازة$captureText. حصل ${piece.owner.label} على دور إضافي"
            else -> "تم تحريك القطعة$captureText. الدور الآن لـ ${nextTurn.label}"
        }

        return state.copy(
            pieces = movedPieces,
            currentTurn = nextTurn,
            canRoll = true,
            availablePieceIds = emptySet(),
            lastMove = LudoMove(
                pieceId = piece.id,
                fromProgress = piece.progress,
                toProgress = targetProgress,
                capturedPieceIds = captureIds,
            ),
            winner = winner,
            statusMessage = status,
        )
    }

    fun skipTurn(state: LudoUiState): LudoUiState {
        if (state.canRoll || state.winner != null) return state

        val nextTurn = nextTurnAfter(state, dice = 1)
        return state.copy(
            currentTurn = nextTurn,
            canRoll = true,
            availablePieceIds = emptySet(),
            statusMessage = "انتهى الوقت. الدور الآن لـ ${nextTurn.label}",
        )
    }

    fun targetProgressFor(piece: LudoPiece, dice: Int): Int? =
        targetProgress(piece.progress, dice)

    fun reset(mode: LudoGameMode): LudoUiState = newGame(mode)

    private fun nextFairDice(): Int {
        val dice = if (rollsSinceSix >= MAX_ROLLS_WITHOUT_SIX) {
            6
        } else {
            random.nextInt(from = 1, until = 7)
        }

        rollsSinceSix = if (dice == 6) 0 else rollsSinceSix + 1
        return dice
    }

    fun chooseBotPiece(state: LudoUiState): Int? {
        val dice = state.diceValue ?: return null
        return state.availablePieceIds
            .mapNotNull { id ->
                val piece = state.pieces.firstOrNull { it.id == id } ?: return@mapNotNull null
                val target = targetProgress(piece.progress, dice) ?: return@mapNotNull null
                BotCandidate(
                    pieceId = id,
                    finishes = target == FINISHED_PROGRESS,
                    captures = capturedPieceIds(state, piece, target).size,
                    leavesHome = piece.progress == HOME_PROGRESS,
                    targetProgress = target,
                )
            }
            .maxWithOrNull(
                compareBy<BotCandidate> { it.finishes }
                    .thenBy { it.captures }
                    .thenBy { it.leavesHome }
                    .thenBy { it.targetProgress },
            )
            ?.pieceId
    }

    private fun movablePieceIds(
        state: LudoUiState,
        player: LudoPlayerColor,
        dice: Int,
    ): Set<Int> = state.pieces
        .filter { piece -> piece.owner == player && targetProgress(piece.progress, dice) != null }
        .map { it.id }
        .toSet()

    private fun targetProgress(currentProgress: Int, dice: Int): Int? = when {
        currentProgress == HOME_PROGRESS && dice == 6 -> FIRST_TRACK_PROGRESS
        currentProgress == HOME_PROGRESS -> null
        currentProgress == FINISHED_PROGRESS -> null
        currentProgress + dice <= FINISHED_PROGRESS -> currentProgress + dice
        else -> null
    }

    private fun capturedPieceIds(
        state: LudoUiState,
        movingPiece: LudoPiece,
        targetProgress: Int,
    ): List<Int> {
        if (targetProgress !in FIRST_TRACK_PROGRESS..LAST_TRACK_PROGRESS) return emptyList()

        val targetCell = absoluteTrackCell(movingPiece.owner, targetProgress)
        if (targetCell in SAFE_TRACK_CELLS) return emptyList()

        return state.pieces
            .filter { candidate ->
                candidate.owner != movingPiece.owner &&
                    candidate.progress in FIRST_TRACK_PROGRESS..LAST_TRACK_PROGRESS &&
                    absoluteTrackCell(candidate.owner, candidate.progress) == targetCell
            }
            .map { it.id }
    }

    private fun absoluteTrackCell(owner: LudoPlayerColor, progress: Int): Int =
        (owner.startCell + progress) % TRACK_CELL_COUNT

    private fun nextTurnAfter(state: LudoUiState, dice: Int): LudoPlayerColor {
        if (dice == 6) return state.currentTurn

        val currentIndex = state.players.indexOfFirst { it.color == state.currentTurn }
        return state.players[(currentIndex + 1) % state.players.size].color
    }

    private data class BotCandidate(
        val pieceId: Int,
        val finishes: Boolean,
        val captures: Int,
        val leavesHome: Boolean,
        val targetProgress: Int,
    )

    private companion object {
        const val TRACK_CELL_COUNT = 52
        const val MAX_ROLLS_WITHOUT_SIX = 6
        val SAFE_TRACK_CELLS = setOf(1, 9, 14, 22, 27, 35, 40, 47)
    }
}
