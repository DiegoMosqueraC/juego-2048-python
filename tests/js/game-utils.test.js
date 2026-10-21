/**
 * Pruebas unitarias de static/game-utils.js con el ejecutor nativo de Node:
 *   node --test tests/js/*.test.js
 * No requieren instalar dependencias (node:test está incluido desde Node 18).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
    actionForKey,
    swipeDirection,
    tileClassName,
    digitClass,
    statusTransition,
    highestMergedValue
} = require(path.join(__dirname, "..", "..", "static", "game-utils.js"));

test("actionForKey: flechas y WASD producen movimientos", () => {
    assert.deepEqual(actionForKey({ key: "ArrowLeft" }), { type: "move", direction: "left" });
    assert.deepEqual(actionForKey({ key: "d" }), { type: "move", direction: "right" });
    assert.deepEqual(actionForKey({ key: "W" }), { type: "move", direction: "up" });
    assert.deepEqual(actionForKey({ key: "ArrowDown" }), { type: "move", direction: "down" });
});

test("actionForKey: U deshace y R reinicia", () => {
    assert.deepEqual(actionForKey({ key: "u" }), { type: "undo" });
    assert.deepEqual(actionForKey({ key: "R" }), { type: "reset" });
});

test("actionForKey: BUG-13, Ctrl/Cmd/Alt + tecla no activan atajos del juego", () => {
    assert.equal(actionForKey({ key: "r", ctrlKey: true }), null);
    assert.equal(actionForKey({ key: "r", metaKey: true }), null);
    assert.equal(actionForKey({ key: "ArrowLeft", altKey: true }), null);
});

test("actionForKey: teclas sin función y eventos vacíos se ignoran", () => {
    assert.equal(actionForKey({ key: "x" }), null);
    assert.equal(actionForKey({ key: "Enter" }), null);
    assert.equal(actionForKey(undefined), null);
});

test("swipeDirection: gestos cortos no cuentan (valor límite)", () => {
    assert.equal(swipeDirection(34, 0, 35), null);
    assert.equal(swipeDirection(35, 0, 35), "right");
    assert.equal(swipeDirection(0, 0, 35), null);
});

test("swipeDirection: domina el eje con mayor desplazamiento", () => {
    assert.equal(swipeDirection(-80, 10, 35), "left");
    assert.equal(swipeDirection(5, 60, 35), "down");
    assert.equal(swipeDirection(5, -60, 35), "up");
    assert.equal(swipeDirection(50, 50, 35), "right"); // empate: horizontal
});

test("tileClassName: hasta la meta usa su color; mayores, el estilo especial", () => {
    assert.equal(tileClassName(2, 2048), "tile-2");
    assert.equal(tileClassName(2048, 2048), "tile-2048");
    assert.equal(tileClassName(4096, 2048), "tile-super");
});

test("digitClass: clase según la cantidad de dígitos, con tope en 6", () => {
    assert.equal(digitClass(2), "digits-1");
    assert.equal(digitClass(1024), "digits-4");
    assert.equal(digitClass(131072), "digits-6");
    assert.equal(digitClass(1048576), "digits-6");
});

test("statusTransition: BUG-14, solo se anuncia al entrar en un estado", () => {
    assert.equal(statusTransition("playing", "won"), "won");
    assert.equal(statusTransition("playing", "game_over"), "game_over");
    assert.equal(statusTransition("won", "won"), null);
    assert.equal(statusTransition("game_over", "game_over"), null);
    assert.equal(statusTransition("game_over", "playing"), null);
});

test("highestMergedValue: valor mayor entre las celdas fusionadas", () => {
    const grid = [[4, 0], [16, 8]];
    assert.equal(highestMergedValue(grid, []), 0);
    assert.equal(highestMergedValue(grid, undefined), 0);
    assert.equal(highestMergedValue(grid, [[0, 0], [1, 0]]), 16);
});
