package com.example.ludo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LudoGameEngineTest {
    private val engine = LudoGameEngine()

    @Test
    fun rollingSixAllowsPiecesToLeaveHome() {
        val initialState = engine.newGame(LudoGameMode.Solo)

        val rolled = engine.rollDice(initialState, forcedValue = 6)
        val moved = engine.movePiece(rolled, pieceId = 0)

        assertFalse(rolled.canRoll)
        assertEquals(setOf(0, 1, 2, 3), rolled.availablePieceIds)
        assertEquals(FIRST_TRACK_PROGRESS, moved.pieces.first { it.id == 0 }.progress)
        assertEquals(LudoPlayerColor.Yellow, moved.currentTurn)
    }

    @Test
    fun rollingWithoutAvailableMoveAdvancesTurn() {
        val initialState = engine.newGame(LudoGameMode.FourPlayers)

        val rolled = engine.rollDice(initialState, forcedValue = 3)

        assertFalse(rolled.canRoll)
        assertEquals(emptySet<Int>(), rolled.availablePieceIds)
        assertEquals(LudoPlayerColor.Yellow, rolled.currentTurn)

        val skipped = engine.skipTurn(rolled)
        assertTrue(skipped.canRoll)
        assertEquals(LudoPlayerColor.Blue, skipped.currentTurn)
    }

    @Test
    fun movingToOccupiedUnsafeCellCapturesOpponent() {
        val initialState = engine.newGame(LudoGameMode.FourPlayers)
        val pieces = initialState.pieces.map { piece ->
            when (piece.id) {
                0 -> piece.copy(progress = 4)
                4 -> piece.copy(progress = 19)
                else -> piece
            }
        }
        val readyToMove = initialState.copy(
            pieces = pieces,
            currentTurn = LudoPlayerColor.Yellow,
            diceValue = 2,
            canRoll = false,
            availablePieceIds = setOf(0),
        )

        val moved = engine.movePiece(readyToMove, pieceId = 0)

        assertEquals(6, moved.pieces.first { it.id == 0 }.progress)
        assertEquals(HOME_PROGRESS, moved.pieces.first { it.id == 4 }.progress)
        assertEquals(listOf(4), moved.lastMove?.capturedPieceIds)
    }
}
