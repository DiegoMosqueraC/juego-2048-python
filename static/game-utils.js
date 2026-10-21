/**
 * game-utils.js - Funciones puras de la interfaz web de 2048
 * ==========================================================
 * No tocan el DOM ni la red, por eso se prueban con el ejecutor de pruebas de
 * Node (node --test "tests/js/*.test.js") y se reutilizan en el navegador desde app.js.
 */
(function (root) {
    "use strict";

    const KEY_TO_DIRECTION = {
        ArrowLeft: "left", a: "left", A: "left",
        ArrowRight: "right", d: "right", D: "right",
        ArrowUp: "up", w: "up", W: "up",
        ArrowDown: "down", s: "down", S: "down"
    };
    const KEY_TO_COMMAND = { u: "undo", U: "undo", r: "reset", R: "reset" };
    const MAX_DIGIT_CLASS = 6;

    /**
     * Traduce una pulsación de teclado a una acción del juego.
     * Ignora las combinaciones con Ctrl, Cmd o Alt (BUG-13: Ctrl+R recargaba la
     * página y además reiniciaba la partida).
     * @returns {{type: string, direction?: string} | null}
     */
    function actionForKey(event) {
        if (!event || event.ctrlKey || event.metaKey || event.altKey) {
            return null;
        }
        if (KEY_TO_DIRECTION[event.key]) {
            return { type: "move", direction: KEY_TO_DIRECTION[event.key] };
        }
        if (KEY_TO_COMMAND[event.key]) {
            return { type: KEY_TO_COMMAND[event.key] };
        }
        return null;
    }

    /**
     * Dirección de un deslizamiento táctil, o null si es demasiado corto.
     * @param {number} deltaX desplazamiento horizontal en píxeles
     * @param {number} deltaY desplazamiento vertical en píxeles
     * @param {number} threshold distancia mínima para considerarlo un gesto
     */
    function swipeDirection(deltaX, deltaY, threshold) {
        const horizontal = Math.abs(deltaX) >= Math.abs(deltaY);
        const distance = horizontal ? Math.abs(deltaX) : Math.abs(deltaY);
        if (distance < threshold) {
            return null;
        }
        if (horizontal) {
            return deltaX > 0 ? "right" : "left";
        }
        return deltaY > 0 ? "down" : "up";
    }

    /** Clase CSS del color de una ficha; las mayores que la meta comparten estilo. */
    function tileClassName(value, winningTile) {
        return value <= winningTile ? `tile-${value}` : "tile-super";
    }

    /** Clase CSS según la cantidad de dígitos, para ajustar el tamaño de letra. */
    function digitClass(value) {
        const digits = Math.min(String(value).length, MAX_DIGIT_CLASS);
        return `digits-${digits}`;
    }

    /**
     * Evento que debe anunciarse al cambiar de estado. Devuelve "won" o
     * "game_over" solo cuando se ENTRA en ese estado (BUG-14: antes el sonido y
     * el aviso se repetían en cada actualización de la pantalla).
     */
    function statusTransition(previousStatus, nextStatus) {
        if (nextStatus === previousStatus || nextStatus === "playing") {
            return null;
        }
        return nextStatus;
    }

    /** Valor más alto entre las celdas que se fusionaron en la jugada. */
    function highestMergedValue(grid, mergedCells) {
        return (mergedCells || []).reduce(
            (highest, [row, col]) => Math.max(highest, grid[row][col]), 0
        );
    }

    const api = {
        actionForKey,
        swipeDirection,
        tileClassName,
        digitClass,
        statusTransition,
        highestMergedValue
    };

    if (typeof module === "object" && module.exports) {
        module.exports = api;
    } else {
        root.GameUtils = api;
    }
})(typeof globalThis !== "undefined" ? globalThis : this);
