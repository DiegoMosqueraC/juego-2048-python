/**
 * app.js - Cliente web del juego 2048
 * ===================================
 * Se comunica con la API de Python, dibuja el tablero con animaciones de
 * deslizamiento, reproduce sonidos sintetizados (Web Audio API) y atiende el
 * teclado, los gestos táctiles y los botones. Las decisiones puras (qué tecla
 * es qué acción, cuándo anunciar una victoria...) viven en game-utils.js.
 */
"use strict";

const {
    actionForKey,
    swipeDirection,
    tileClassName,
    digitClass,
    statusTransition,
    highestMergedValue
} = window.GameUtils;

// Debe coincidir con --slide-duration en style.css.
const SLIDE_DURATION_MS = 110;
const SWIPE_THRESHOLD_PX = 35;
const SCORE_BUBBLE_MS = 850;
// Debe coincidir con STONE en config.py: celda bloqueada del modo expedición.
const STONE = -1;
const EVENT_MS = 2600;
const EVENT_TEXTS = {
    terremoto: "¡Terremoto! El tablero se sacudió solo.",
    fenix: "¡El Fénix te salvó! Se borraron los 2 y los 4.",
    escudo: "El escudo anuló las maldiciones de este piso.",
    crece: "¡La mina se ensancha! El tablero creció una fila y una columna."
};
const JSON_HEADERS = { "Content-Type": "application/json" };
const CONNECTION_ERROR = "Sin conexión con el servidor de Python. "
    + "Verifica que la terminal del juego siga abierta.";
const DIRECTION_PHRASES = {
    left: "a la izquierda",
    right: "a la derecha",
    up: "hacia arriba",
    down: "hacia abajo"
};

// -----------------------------------------------------------------------------
// Preferencias del usuario
// -----------------------------------------------------------------------------
// localStorage lanza excepciones en modo privado o con el almacenamiento
// bloqueado (BUG-16); en ese caso el juego funciona sin recordar preferencias.
const preferences = {
    get(key, fallback) {
        try {
            const value = window.localStorage.getItem(key);
            return value === null ? fallback : value;
        } catch (error) {
            return fallback;
        }
    },
    set(key, value) {
        try {
            window.localStorage.setItem(key, String(value));
        } catch (error) {
            // Sin almacenamiento disponible: la preferencia dura solo esta sesión.
        }
    }
};

const SVG_NS = "http://www.w3.org/2000/svg";
const NUMBER_TWEEN_MS = 420;
const COINS_PER_RAIN = 14;

/** Crea un <svg> que usa un icono del sprite de index.html. */
function icon(name, className = "icon") {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", `#${name}`);
    svg.appendChild(use);
    return svg;
}

/** Elemento con clase y texto opcionales. */
function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

/** Reinicia una animación CSS de clase `name` aunque ya se esté mostrando. */
function replayClass(node, name) {
    node.classList.remove(name);
    void node.offsetWidth; // Fuerza al navegador a notar el cambio.
    node.classList.add(name);
}

function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// -----------------------------------------------------------------------------
// Efectos de sonido sintetizados (Web Audio API)
// -----------------------------------------------------------------------------
class SoundEffects {
    constructor() {
        this.context = null;
        this.enabled = preferences.get("2048_sound", "true") !== "false";
    }

    toggle() {
        this.enabled = !this.enabled;
        preferences.set("2048_sound", this.enabled);
        return this.enabled;
    }

    _audioContext() {
        if (!this.enabled) {
            return null;
        }
        if (!this.context) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) {
                return null;
            }
            this.context = new AudioContextClass();
        }
        if (this.context.state === "suspended") {
            this.context.resume();
        }
        return this.context;
    }

    /** Reproduce un tono con caída exponencial de volumen. */
    _tone({ type, from, to = from, volume, duration, delay = 0 }) {
        const context = this._audioContext();
        if (!context) {
            return;
        }
        const start = context.currentTime + delay;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(from, start);
        if (to !== from) {
            oscillator.frequency.exponentialRampToValueAtTime(to, start + duration);
        }
        gain.gain.setValueAtTime(volume, start);
        gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(start);
        oscillator.stop(start + duration);
    }

    playMove() {
        this._tone({ type: "sine", from: 160, to: 80, volume: 0.12, duration: 0.08 });
    }

    /** Las fusiones de fichas más altas suenan más agudas. */
    playMerge(value) {
        const base = 260 + Math.min(Math.log2(value || 4) * 55, 600);
        this._tone({ type: "triangle", from: base, to: base * 1.5, volume: 0.2, duration: 0.14 });
    }

    playWin() {
        // Arpegio Do - Mi - Sol - Do agudo.
        [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) => {
            this._tone({ type: "sine", from: frequency, volume: 0.25, duration: 0.35, delay: index * 0.1 });
        });
    }

    playGameOver() {
        this._tone({ type: "sawtooth", from: 220, to: 110, volume: 0.18, duration: 0.4 });
    }

    /** Dos notas agudas y cortas, como monedas que chocan. */
    playCoin() {
        this._tone({ type: "square", from: 988, volume: 0.08, duration: 0.08 });
        this._tone({ type: "square", from: 1319, volume: 0.08, duration: 0.22, delay: 0.07 });
    }

    playCard() {
        this._tone({ type: "triangle", from: 420, to: 840, volume: 0.15, duration: 0.12 });
    }
}

// -----------------------------------------------------------------------------
// Cliente del juego
// -----------------------------------------------------------------------------
class GameClient {
    constructor() {
        this.sound = new SoundEffects();
        this.el = {
            board: document.getElementById("game-board"),
            gridBackground: document.getElementById("grid-background"),
            tiles: document.getElementById("tile-container"),
            score: document.getElementById("current-score"),
            best: document.getElementById("best-score"),
            bubbles: document.getElementById("score-bubble-container"),
            goal: document.getElementById("goal-tile"),
            toast: document.getElementById("toast"),
            announcer: document.getElementById("announcer"),
            undo: document.getElementById("btn-undo"),
            soundButton: document.getElementById("btn-sound"),
            themeButton: document.getElementById("btn-theme"),
            expeditionBar: document.getElementById("expedition-bar"),
            blessingCards: document.getElementById("blessing-cards"),
            fx: document.getElementById("fx-layer")
        };
        this.modals = {
            win: document.getElementById("modal-win"),
            over: document.getElementById("modal-over"),
            confirm: document.getElementById("modal-confirm"),
            choose: document.getElementById("modal-choose")
        };
        this.state = null;
        this.size = 0;
        this.tileElements = new Map();
        this.busy = false;
        this.pendingDirection = null;
        this.focusBeforeModal = null;
        // Valores mostrados en pantalla: se animan hasta el valor real.
        this.shown = { score: 0, gold: 0 };
        this.offerKey = "";
        // Textos originales de los diálogos: la expedición los cambia y el
        // modo clásico debe recuperarlos al volver.
        this.dialogDefaults = ["win-title", "win-text", "over-title", "over-text"].map(
            (id) => [id, document.getElementById(id).cloneNode(true)]);

        this.setupKeyboard();
        this.setupButtons();
        this.setupTouch();
        this.applyTheme(this.savedTheme());
        this.updateSoundButton();
        this.loadState();
    }

    // --- Comunicación con la API ----------------------------------------------

    /**
     * GET si no hay cuerpo; POST con JSON si lo hay.
     * @returns {Promise<{ok: boolean, status: number, data: object} | null>}
     *          null si el servidor no respondió.
     */
    async request(path, body) {
        const options = body === undefined
            ? { cache: "no-store" }
            : { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) };
        let response;
        try {
            response = await fetch(path, options);
        } catch (error) {
            this.showToast(CONNECTION_ERROR);
            return null;
        }
        this.hideToast();
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            // Respuesta sin JSON: se informa con el código de estado.
        }
        return { ok: response.ok, status: response.status, data };
    }

    async loadState() {
        const result = await this.request("/api/state");
        if (result && result.ok) {
            this.applyState(result.data, { appear: true });
        }
    }

    async move(direction) {
        if (this.openModalName()) {
            return;
        }
        if (this.busy) {
            // Se recuerda la última dirección pedida para no perder pulsaciones rápidas.
            this.pendingDirection = direction;
            return;
        }
        this.busy = true;
        try {
            const result = await this.request("/api/move", { direction });
            if (result && result.ok && result.data.moved) {
                await this.animateSlide(result.data.tile_moves);
                this.playMoveSound(result.data);
                this.applyState(result.data, { move: result.data });
                this.playMoveEffects(result.data);
                this.announceMove(direction, result.data);
            }
        } finally {
            this.busy = false;
            const next = this.pendingDirection;
            this.pendingDirection = null;
            if (next) {
                this.move(next);
            }
        }
    }

    async undo() {
        if (this.busy) {
            return;
        }
        this.busy = true;
        try {
            const result = await this.request("/api/undo", {});
            if (result && result.ok && result.data.undone) {
                this.applyState(result.data, { undo: true });
                this.sound.playMove();
                this.announce(`Jugada deshecha. Puntuación: ${result.data.score}.`);
            }
        } finally {
            this.busy = false;
        }
    }

    /** Pide confirmación si hay una partida en curso con puntos (BUG-13). */
    requestReset() {
        const inProgress = this.state && this.state.status === "playing" && this.state.score > 0;
        if (inProgress) {
            this.toggleModal("confirm", true);
        } else {
            this.reset();
        }
    }

    async reset() {
        this.toggleModal("confirm", false);
        const result = await this.request("/api/reset", {});
        if (result && result.ok) {
            this.applyState(result.data, { appear: true });
            this.sound.playMove();
            this.announce("Nueva partida iniciada.");
        }
    }

    /** Toma gratis la carta `index` de la oferta y abre la tienda. */
    async choose(index) {
        const result = await this.request("/api/choose", { index });
        if (result && result.ok) {
            this.applyState(result.data, {});
            this.sound.playCard();
            this.announce(`Carta tomada. Tienda abierta: tienes ${result.data.expedition.gold} de oro.`);
        }
    }

    /** buy (comprar la carta `index`), reroll (renovar) o leave (bajar de piso). */
    async shopAction(action, index) {
        const result = await this.request("/api/shop", { action, index });
        if (!result) {
            return;
        }
        if (!result.ok) {
            this.announce(result.data.error || "No se pudo completar la compra.");
            return;
        }
        this.applyState(result.data, {});
        const info = result.data.expedition;
        if (action === "leave") {
            this.sound.playMove();
            const curses = info.curses.map((curse) => `${curse.name}: ${curse.description}`).join(" ");
            this.announce(`Piso ${info.floor}, objetivo ${info.target}. ${curses}`);
        } else {
            this.sound.playCoin();
            this.announce(`Te quedan ${info.gold} de oro.`);
        }
    }

    /** Cambia de modo; cada modo conserva su partida en el servidor. */
    async switchMode(mode) {
        if (this.busy || (this.state && this.state.mode === mode)) {
            return;
        }
        const result = await this.request("/api/mode", { mode });
        if (result && result.ok) {
            this.applyState(result.data, { appear: true });
            this.sound.playMove();
            const name = mode === "expedition" ? "Expedición" : "Clásico";
            this.announce(`Modo ${name}. Puntuación: ${result.data.score}.`);
        }
    }

    async continuePlaying() {
        const result = await this.request("/api/continue", {});
        if (result && (result.ok || result.status === 409)) {
            await this.loadState();
        }
    }

    // --- Dibujo del tablero ------------------------------------------------------

    /**
     * Actualiza toda la interfaz con un estado del servidor.
     * @param {object} options move: datos de la jugada (animaciones de fusión y
     *        ficha nueva); appear: anima la aparición de todas las fichas.
     */
    applyState(state, options) {
        const firstLoad = this.state === null;
        const previousStatus = firstLoad ? state.status : this.state.status;
        const cardEffect = !options.move && !options.appear && !options.undo;
        if (!firstLoad && cardEffect && state.size === this.state.size) {
            this.puffRemovedTiles(this.state.grid, state.grid);
        }
        if (state.size !== this.size) {
            this.buildGrid(state.size);
        }
        this.state = state;
        this.updateScores(state, options.move);
        this.renderTiles(state, options);
        document.querySelectorAll(".mode-btn").forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.mode === state.mode));
        });
        this.updateExpedition(state);
        this.updateDialogs(previousStatus, state, firstLoad);
        this.el.undo.disabled = !state.can_undo;
        this.el.goal.textContent = state.expedition ? state.expedition.target : state.winning_tile;
    }

    /** Muestra la barra del modo expedición (piso, recursos, maldiciones y mazo). */
    updateExpedition(state) {
        const info = state.expedition;
        this.el.expeditionBar.classList.toggle("hidden", !info);
        document.querySelector(".expedition-help").classList.toggle("hidden", !info);
        this.el.board.classList.toggle("fog", Boolean(info) && info.curses.some((c) => c.id === "niebla"));
        if (!info) {
            this.el.undo.title = "Deshacer jugada (U)";
            return;
        }
        const set = (id, text) => { document.getElementById(id).textContent = text; };
        const number = (value) => value.toLocaleString("es-CO");
        set("exp-floor", `${info.floor}/${info.floors}`);
        set("exp-target", info.target);
        set("exp-streak", `×${number(info.streak_bonus)}`);
        set("exp-undo", info.undo_charges);
        set("exp-multiplier", `×${number(info.multiplier)}`);
        set("exp-seed", info.seed);
        this.el.expeditionBar.classList.toggle("guardian", info.guardian);

        // Oro: cuenta hacia arriba y la moneda gira cuando sube.
        const goldBox = document.getElementById("exp-gold-box");
        if (info.gold > this.shown.gold) {
            replayClass(goldBox, "gain");
        }
        this.tweenNumber(document.getElementById("exp-gold"), "gold", info.gold);

        // Racha: la llama crece con --heat y arde desde 3 fusiones seguidas.
        const streakBox = document.getElementById("exp-streak-box");
        streakBox.style.setProperty("--heat", Math.min(info.streak / 10, 1));
        streakBox.classList.toggle("hot", info.streak >= 3);

        const movesBox = document.getElementById("exp-moves-box");
        movesBox.classList.toggle("hidden", info.moves_left === null);
        movesBox.classList.toggle("low", info.moves_left !== null && info.moves_left <= 10);
        set("exp-moves", info.moves_left === null ? "" : info.moves_left);

        document.getElementById("exp-curse-list").replaceChildren(...info.curses.map((curse) => {
            const chip = el("li", `chip ${curse.id === "calma" ? "chip-calm" : "chip-curse"}`);
            chip.title = curse.description;
            chip.append(icon(`i-curse-${curse.id}`), curse.name);
            return chip;
        }));
        set("exp-curse-text", info.curses.map((curse) => curse.description).join(" "));
        document.getElementById("exp-deck").replaceChildren(...info.deck.map((card) => {
            const chip = el("li", `chip chip-${card.rarity}`);
            chip.title = card.name;
            chip.append(icon(`i-card-${card.id}`), card.name);
            if (card.count > 1) {
                chip.append(el("span", "chip-count", `×${card.count}`));
            }
            return chip;
        }));
        this.el.undo.title = `Deshacer jugada (U): quedan ${info.undo_charges} usos`;
        this.showEvent(info.event);
        this.renderOffer(state);
    }

    /** Aviso breve de un suceso (terremoto, fénix, escudo) con su efecto en el tablero. */
    showEvent(event) {
        const banner = document.getElementById("exp-event");
        clearTimeout(this.eventTimer);
        banner.classList.toggle("hidden", !event);
        if (!event) {
            return;
        }
        banner.textContent = EVENT_TEXTS[event];
        this.announce(EVENT_TEXTS[event]);
        replayClass(this.el.board, event === "terremoto" ? "shake" : `flash-${event}`);
        this.eventTimer = setTimeout(() => banner.classList.add("hidden"), EVENT_MS);
    }

    /** Cartas para elegir gratis o, después, la tienda con precios en oro. */
    renderOffer(state) {
        const info = state.expedition;
        const shop = state.status === "shop";
        const offering = shop || state.status === "choosing";
        const items = shop ? info.shop.items : info.choices;
        // Solo se vuelven a repartir si cambió algo: así la animación no se repite.
        const key = JSON.stringify([state.status, info.gold, items.map((item) => item.id)]);
        if (!offering || key === this.offerKey) {
            this.offerKey = offering ? key : "";
            return;
        }
        this.offerKey = key;
        const set = (id, text) => { document.getElementById(id).textContent = text; };
        if (shop) {
            set("choose-badge", "Tienda");
            set("choose-title", `Tienes ${info.gold} de oro`);
            set("choose-text", items.length > 0
                ? "Compra las cartas que no elegiste o renueva la oferta."
                : "No quedan cartas: renueva la oferta o sigue bajando.");
        } else {
            const { gold, interest } = info.reward;
            set("choose-badge", info.guardian ? "Guardián vencido" : `Piso ${info.floor} superado`);
            set("choose-title", "Elige una carta gratis");
            set("choose-text", `Ganaste ${gold} de oro${interest ? ` y ${interest} de interés` : ""}. `
                + "Las otras dos cartas quedarán en la tienda.");
        }
        const cards = items.map((item, index) => {
            const card = el("button", `blessing-card rarity-${item.rarity}`);
            card.style.setProperty("--i", index);
            const iconBox = el("span", "card-icon");
            iconBox.append(icon(`i-card-${item.id}`));
            const meta = el("span", "card-meta");
            meta.append(el("span", "card-rarity", item.rarity_name));
            const price = el("span", "card-price");
            if (shop) {
                price.append(icon("i-coin"), String(item.price));
            } else {
                price.textContent = "Gratis";
            }
            meta.append(price);
            card.append(el("span", "card-key", String(index + 1)), iconBox,
                el("span", "blessing-name", item.name), el("span", "blessing-text", item.description), meta);
            card.setAttribute("aria-label", `${item.name}, carta ${item.rarity_name.toLowerCase()}. `
                + `${item.description} ${shop ? `Cuesta ${item.price} de oro.` : "Gratis."}`);
            card.disabled = shop && info.gold < item.price;
            card.addEventListener("click", () => (shop ? this.shopAction("buy", index) : this.choose(index)));
            return card;
        });
        this.el.blessingCards.replaceChildren(...cards);
        document.getElementById("shop-actions").classList.toggle("hidden", !shop);
        const reroll = document.getElementById("btn-reroll");
        reroll.replaceChildren(icon("i-restart"), `Renovar la oferta (${info.shop.reroll_price} de oro)`);
        reroll.disabled = info.gold < info.shop.reroll_price;
        document.getElementById("btn-leave-shop").replaceChildren(icon("i-stairs"), `Bajar al piso ${info.floor + 1}`);
        // Al cambiar las cartas con el diálogo abierto, el foco no debe perderse.
        const modal = this.modals.choose;
        if (!modal.classList.contains("hidden") && !modal.contains(document.activeElement)) {
            modal.querySelector("button:not(:disabled)").focus();
        }
    }

    /** Genera las celdas de fondo para un tablero de size x size. */
    buildGrid(size) {
        this.size = size;
        this.el.board.style.setProperty("--size", size);
        const cells = Array.from({ length: size * size }, () => {
            const cell = document.createElement("div");
            cell.className = "grid-cell";
            return cell;
        });
        this.el.gridBackground.replaceChildren(...cells);
    }

    createTile(value, row, col) {
        const tile = document.createElement("div");
        tile.className = value === STONE
            ? "tile tile-stone"
            : `tile ${tileClassName(value, this.state.winning_tile)} ${digitClass(value)}`;
        tile.style.setProperty("--row", row);
        tile.style.setProperty("--col", col);
        const inner = document.createElement("div");
        inner.className = "tile-inner";
        inner.textContent = value === STONE ? "" : value;
        tile.appendChild(inner);
        return tile;
    }

    renderTiles(state, { move, appear }) {
        const merged = new Set((move ? move.merged_cells : []).map(([r, c]) => `${r},${c}`));
        const newTile = move && move.new_tile ? `${move.new_tile.row},${move.new_tile.col}` : null;
        const tiles = [];
        this.tileElements.clear();
        state.grid.forEach((rowValues, row) => {
            rowValues.forEach((value, col) => {
                if (!value) {
                    return;
                }
                const key = `${row},${col}`;
                const tile = this.createTile(value, row, col);
                if (appear || key === newTile) {
                    tile.classList.add("tile-new");
                } else if (merged.has(key)) {
                    tile.classList.add("tile-merged");
                }
                this.tileElements.set(key, tile);
                tiles.push(tile);
            });
        });
        this.el.tiles.replaceChildren(...tiles);
    }

    /**
     * Desliza cada ficha desde su celda de origen hasta su destino (BUG-12: antes
     * no había deslizamiento y toda ficha movida "aparecía" como si fuera nueva).
     */
    animateSlide(tileMoves) {
        if (!tileMoves || tileMoves.length === 0 || prefersReducedMotion()) {
            return Promise.resolve();
        }
        tileMoves.forEach(({ from, to }) => {
            const tile = this.tileElements.get(`${from[0]},${from[1]}`);
            if (tile) {
                tile.style.setProperty("--row", to[0]);
                tile.style.setProperty("--col", to[1]);
            }
        });
        return new Promise((resolve) => setTimeout(resolve, SLIDE_DURATION_MS));
    }

    updateScores(state, move) {
        this.tweenNumber(this.el.score, "score", state.score);
        this.el.best.textContent = state.highscore.toLocaleString("es-CO");
        if (move && move.points > 0) {
            this.showScoreBubble(move.points);
            replayClass(this.el.score, "bump");
        }
    }

    /** Cuenta desde el valor mostrado hasta `target` en lugar de saltar. */
    tweenNumber(node, key, target) {
        const from = this.shown[key];
        this.shown[key] = target;
        cancelAnimationFrame(this.tweens?.[key]);
        if (prefersReducedMotion() || from === target) {
            node.textContent = target.toLocaleString("es-CO");
            return;
        }
        this.tweens = this.tweens || {};
        const start = performance.now();
        const step = (now) => {
            const progress = Math.min((now - start) / NUMBER_TWEEN_MS, 1);
            const eased = 1 - (1 - progress) ** 3;
            node.textContent = Math.round(from + (target - from) * eased).toLocaleString("es-CO");
            if (progress < 1) {
                this.tweens[key] = requestAnimationFrame(step);
            }
        };
        this.tweens[key] = requestAnimationFrame(step);
    }

    showScoreBubble(points) {
        const bubble = el("span", "score-bubble", `+${points}`);
        this.el.bubbles.appendChild(bubble);
        setTimeout(() => bubble.remove(), SCORE_BUBBLE_MS);
    }

    // --- Efectos visuales (se omiten con «reducir movimiento») -----------------------

    /** Celda de efectos ubicada sobre la casilla (row, col); se borra sola. */
    fxCell(row, col, lifetime) {
        const cell = el("div", "fx-cell");
        cell.style.setProperty("--row", row);
        cell.style.setProperty("--col", col);
        this.el.fx.appendChild(cell);
        setTimeout(() => cell.remove(), lifetime);
        return cell;
    }

    /** Partículas que salen disparadas desde una casilla. */
    burst(row, col, className, color, count) {
        const cell = this.fxCell(row, col, 800);
        for (let i = 0; i < count; i += 1) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
            const distance = 55 + Math.random() * 35;
            const particle = el("span", className);
            particle.style.setProperty("--dx", `${Math.cos(angle) * distance}cqi`);
            particle.style.setProperty("--dy", `${Math.sin(angle) * distance}cqi`);
            if (color) {
                particle.style.setProperty("--spark", color);
            }
            cell.appendChild(particle);
        }
    }

    /** Chispas del color de cada fusión y los puntos subiendo desde la mayor. */
    playMoveEffects(data) {
        if (prefersReducedMotion() || !data.merged_cells.length) {
            return;
        }
        let best = data.merged_cells[0];
        data.merged_cells.forEach(([row, col]) => {
            const tile = this.tileElements.get(`${row},${col}`);
            const color = tile ? getComputedStyle(tile.firstChild).backgroundColor : null;
            this.burst(row, col, "fx-spark", color, 8);
            if (data.grid[row][col] > data.grid[best[0]][best[1]]) {
                best = [row, col];
            }
        });
        if (data.points > 0) {
            const streak = data.expedition ? data.expedition.streak : 0;
            const heat = streak >= 6 ? 3 : streak >= 3 ? 2 : streak >= 1 ? 1 : 0;
            const label = el("span", `fx-points heat-${data.expedition ? heat : 0}`, `+${data.points}`);
            if (data.expedition && data.expedition.streak_bonus > 1) {
                label.append(el("small", "", `×${data.expedition.streak_bonus.toLocaleString("es-CO")}`));
            }
            this.fxCell(best[0], best[1], 1000).appendChild(label);
        }
    }

    /** Nube de polvo donde una carta borró fichas o piedras. */
    puffRemovedTiles(before, after) {
        if (prefersReducedMotion()) {
            return;
        }
        before.forEach((rowValues, row) => rowValues.forEach((value, col) => {
            if (value && !after[row][col]) {
                this.burst(row, col, "fx-dust", null, 6);
            }
        }));
    }

    /** Lluvia de monedas sobre el tablero al superar un piso. */
    coinRain() {
        this.sound.playCoin();
        if (prefersReducedMotion()) {
            return;
        }
        for (let i = 0; i < COINS_PER_RAIN; i += 1) {
            const coin = icon("i-coin", "icon fx-coin");
            coin.style.setProperty("left", `${4 + Math.random() * 86}%`);
            coin.style.setProperty("animation-delay", `${Math.random() * 0.45}s`);
            this.el.fx.appendChild(coin);
            setTimeout(() => coin.remove(), 1900);
        }
    }

    playMoveSound(data) {
        const mergedValue = highestMergedValue(data.grid, data.merged_cells);
        if (mergedValue > 0) {
            this.sound.playMerge(mergedValue);
        } else {
            this.sound.playMove();
        }
    }

    // --- Diálogos y anuncios -------------------------------------------------------

    /** Muestra u oculta los diálogos de victoria y fin, y anuncia los cambios. */
    updateDialogs(previousStatus, state, firstLoad) {
        // Sin historial (p. ej., tras recargar la página) no hay jugada que deshacer.
        document.getElementById("btn-over-undo").disabled = !state.can_undo;
        this.updateDialogTexts(state);
        if (!state.expedition) {
            // Va después de updateDialogTexts, que restaura el texto original.
            document.getElementById("final-score-text").textContent = state.score.toLocaleString("es-CO");
        }
        this.toggleModal("win", state.status === "won");
        this.toggleModal("over", state.status === "game_over");
        this.toggleModal("choose", state.status === "choosing" || state.status === "shop");
        // BUG-14: sonido y anuncio solo al ENTRAR en el estado, nunca al recargar.
        const transition = firstLoad ? null : statusTransition(previousStatus, state.status);
        if (transition === "choosing") {
            this.sound.playWin();
            this.coinRain();
            this.announce(`Piso ${state.expedition.floor} superado. Ganaste `
                + `${state.expedition.reward.gold} de oro. Elige una carta gratis con las teclas 1, 2 o 3.`);
        } else if (transition === "won") {
            this.sound.playWin();
            this.announce("¡Felicitaciones! Alcanzaste la ficha 2048.");
        } else if (transition === "game_over") {
            this.sound.playGameOver();
            this.announce(`Fin de la partida. Puntuación final: ${state.score}.`);
        }
    }

    /** En la expedición los diálogos de victoria y derrota cuentan otra historia. */
    updateDialogTexts(state) {
        const info = state.expedition;
        const set = (id, text) => { document.getElementById(id).textContent = text; };
        document.getElementById("btn-continue").classList.toggle("hidden", Boolean(info));
        if (!info) {
            this.dialogDefaults.forEach(([id, original]) => {
                document.getElementById(id).replaceChildren(
                    ...original.cloneNode(true).childNodes);
            });
            return;
        }
        const cards = info.deck.reduce((total, card) => total + card.count, 0);
        const summary = `${state.score.toLocaleString("es-CO")} puntos, ${info.gold} de oro, `
            + `racha máxima de ${info.best_streak} y ${cards} cartas. Semilla: ${info.seed}.`;
        set("win-title", "¡Expedición completada!");
        set("win-text", `Superaste los ${info.floors} pisos y llegaste al 2048 con ${summary}`);
        set("over-title", info.moves_left === 0 ? "¡Se acabó el tiempo!" : "¡La expedición terminó!");
        set("over-text", `Llegaste al piso ${info.floor} de ${info.floors} con ${summary}`);
    }

    openModalName() {
        return Object.keys(this.modals).find((name) => !this.modals[name].classList.contains("hidden"));
    }

    toggleModal(name, open) {
        const modal = this.modals[name];
        const isOpen = !modal.classList.contains("hidden");
        if (open === isOpen) {
            return;
        }
        if (open) {
            this.focusBeforeModal = document.activeElement;
            modal.classList.remove("hidden");
            modal.querySelector("button").focus();
        } else {
            modal.classList.add("hidden");
            if (this.focusBeforeModal && document.contains(this.focusBeforeModal)) {
                this.focusBeforeModal.focus();
            }
        }
    }

    /** Escape cierra la confirmación y Tab no sale del diálogo abierto. */
    handleModalKey(event, name) {
        if (name === "choose" && ["1", "2", "3"].includes(event.key)) {
            const card = this.el.blessingCards.children[Number(event.key) - 1];
            if (card && !card.disabled) {
                card.click();
            }
            return;
        }
        if (event.key === "Escape" && name === "confirm") {
            this.toggleModal("confirm", false);
            return;
        }
        if (event.key !== "Tab") {
            return;
        }
        const buttons = Array.from(this.modals[name].querySelectorAll("button"));
        const index = buttons.indexOf(document.activeElement);
        const step = event.shiftKey ? -1 : 1;
        event.preventDefault();
        buttons[(index + step + buttons.length) % buttons.length].focus();
    }

    announce(message) {
        this.el.announcer.textContent = message;
    }

    announceMove(direction, data) {
        const points = data.points > 0 ? ` Ganaste ${data.points} puntos.` : "";
        this.announce(`Movimiento ${DIRECTION_PHRASES[direction]}.${points} `
            + `Puntuación: ${data.score}. Ficha mayor: ${data.max_tile}.`);
    }

    showToast(message) {
        this.el.toast.textContent = message;
        this.el.toast.classList.remove("hidden");
    }

    hideToast() {
        this.el.toast.classList.add("hidden");
    }

    // --- Entradas: teclado, botones y gestos ------------------------------------

    setupKeyboard() {
        window.addEventListener("keydown", (event) => {
            const modalName = this.openModalName();
            if (modalName) {
                this.handleModalKey(event, modalName);
                return;
            }
            const action = actionForKey(event);
            if (!action) {
                return;
            }
            event.preventDefault(); // Las flechas no deben desplazar la página.
            if (action.type === "move") {
                this.move(action.direction);
            } else if (action.type === "undo") {
                this.undo();
            } else if (action.type === "reset") {
                this.requestReset();
            }
        });
    }

    setupButtons() {
        const onClick = (id, handler) => document.getElementById(id).addEventListener("click", handler);
        onClick("btn-undo", () => this.undo());
        onClick("btn-restart", () => this.requestReset());
        onClick("btn-continue", () => this.continuePlaying());
        onClick("btn-win-restart", () => this.reset());
        onClick("btn-over-restart", () => this.reset());
        onClick("btn-over-undo", () => this.undo());
        onClick("btn-confirm-restart", () => this.reset());
        onClick("btn-cancel-restart", () => this.toggleModal("confirm", false));
        onClick("btn-sound", () => {
            this.sound.toggle();
            this.updateSoundButton();
        });
        onClick("btn-theme", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            preferences.set("2048_theme", next);
            this.applyTheme(next);
        });
        onClick("btn-reroll", () => this.shopAction("reroll"));
        onClick("btn-leave-shop", () => this.shopAction("leave"));
        document.querySelectorAll(".mode-btn").forEach((button) => {
            button.addEventListener("click", () => this.switchMode(button.dataset.mode));
        });
        document.querySelectorAll(".dpad-btn").forEach((button) => {
            button.addEventListener("click", () => this.move(button.dataset.dir));
        });
    }

    setupTouch() {
        let startX = 0;
        let startY = 0;
        this.el.board.addEventListener("touchstart", (event) => {
            startX = event.changedTouches[0].clientX;
            startY = event.changedTouches[0].clientY;
        }, { passive: true });
        this.el.board.addEventListener("touchend", (event) => {
            const touch = event.changedTouches[0];
            const direction = swipeDirection(touch.clientX - startX, touch.clientY - startY,
                SWIPE_THRESHOLD_PX);
            if (direction) {
                this.move(direction);
            }
        }, { passive: true });
    }

    // --- Preferencias visuales ------------------------------------------------------

    savedTheme() {
        const systemTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
        return preferences.get("2048_theme", systemTheme);
    }

    applyTheme(theme) {
        const dark = theme === "dark";
        document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
        this.el.themeButton.setAttribute("aria-pressed", String(dark));
        document.getElementById("icon-moon").classList.toggle("hidden", !dark);
        document.getElementById("icon-sun").classList.toggle("hidden", dark);
    }

    updateSoundButton() {
        const enabled = this.sound.enabled;
        this.el.soundButton.setAttribute("aria-pressed", String(enabled));
        document.getElementById("icon-sound-on").classList.toggle("hidden", !enabled);
        document.getElementById("icon-sound-off").classList.toggle("hidden", enabled);
    }
}

// Los scripts usan "defer": el DOM ya está listo cuando se ejecuta esta línea.
window.gameClient = new GameClient();
