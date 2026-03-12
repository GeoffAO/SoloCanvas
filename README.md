# SoloCanvas

A freeform canvas tool built for solo tabletop RPG players. Place card decks, dice, and images on an infinite canvas, manage your hand, take notes, and save your sessions — all in one window.

> **Platform:** Windows | **Language:** Python 3 + PyQt6 | **License:** GPL-3.0

---

## Features

- **Infinite canvas** — zoom, pan, and arrange anything freely
- **Card decks** — load image-based decks, draw to hand or canvas, flip, shuffle, search, and reorder
- **Dice** — place physical dice on the canvas; roll with a keypress
- **Image import** — drag in images, paste from clipboard, or import via the Image Library
- **Hand strip** — a persistent card hand at the bottom of the window with drag-to-reorder and multi-select
- **Notepad** — a WYSIWYG Markdown notepad with heading formatting and font controls
- **Sessions** — save and load named sessions with canvas screenshots; autosave on close
- **Canvas theming** — the entire UI derives its colour from the canvas background

---

## Installation

### Requirements

- Python 3.10 or newer (3.14 recommended)
- pip

### Steps

1. **Clone or download the repository:**

   ```bash
   git clone https://github.com/GeoffAO/SoloCanvas.git
   cd SoloCanvas
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   Dependencies installed:
   | Package | Purpose |
   |---|---|
   | PyQt6 ≥ 6.5 | UI framework |
   | Pillow ≥ 10.0 | Image processing |
   | qtawesome ≥ 1.3 | Icon fonts |
   | markdown ≥ 3.5 | Notepad rendering |
   | markdownify ≥ 0.11 | Notepad saving |

---

## Launching

### From source

```bash
python main.py
```

Or double-click **`launch.bat`** on Windows — it checks for dependencies, offers to install any that are missing, and launches the app without a terminal window.

### Standalone executable (Windows)

Run **`build.bat`** to produce a self-contained executable using PyInstaller:

```
dist\SoloCanvas\SoloCanvas.exe
```

The build script bundles all dependencies. Copy your `Decks\` folder next to the exe before running.

---

## Adding Decks

SoloCanvas loads card decks from the **`Decks\`** folder next to `main.py` (or the exe).

Each deck is a **subfolder** containing card images and a back image:

```
Decks/
  My Deck/
    card_01.png
    card_02.png
    ...
    back.png          ← must be named "back" (any supported image format)
```

Supported image formats: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.tiff`, `.webp`

The back image is identified by its filename containing the word `back`. All other images in the folder become cards.

---

## The Canvas

### Navigation

| Action | Result |
|---|---|
| Scroll wheel | Zoom in / out |
| Middle-click drag | Pan |
| Right-click drag | Pan |
| Right-click (empty area) | Canvas context menu |

### Selecting Items

| Action | Result |
|---|---|
| Left-click | Select item |
| Ctrl+click | Add to selection |
| Click and drag (empty area) | Rubber-band select |
| Ctrl+A | Select all |

### Moving & Arranging

Items can be freely dragged. To control Z-order (layering):

| Key | Action |
|---|---|
| `U` | Send selected item(s) to the back |
| Left-click any item | Raises it to the top |

### Locking Items

Right-click any item and choose **Lock / Anchor** to pin it in place. Locked items cannot be moved and do not show hover previews.

---

## Cards & Decks

### Placing a Deck

Open the **Deck Library** (`D` key or Tools menu) and double-click a deck to place it on the canvas.

### Drawing Cards

Hover your cursor over a deck on the canvas, then press a number key:

| Key | Action |
|---|---|
| `1` – `9` | Draw that many cards to your **hand** |
| `Shift` + `1`–`9` | Draw cards directly to the **canvas** |

### Card Actions

| Key / Action | Result |
|---|---|
| `F` | Flip selected card(s) or deck(s) face-up / face-down |
| `R` | Shuffle selected deck(s) / roll selected dice |
| `U` | Send selected item(s) to back |
| Double-click card | Flip it |
| Right-click item | Context menu (flip, lock, discard, etc.) |

### The Hand

The **hand strip** runs along the bottom of the window. Cards drawn to the hand appear here.

| Action | Result |
|---|---|
| Click a card | Select it |
| Drag a card to canvas | Place it on the canvas |
| Drag a card within the hand | Reorder the hand |
| Click and drag (empty space) | Rubber-band multi-select |
| Right-click | Hand context menu |

The **LIB** button (left side) opens the Deck Library. The **RCL** button returns canvas cards to their decks.

### Stacking Cards

Select multiple card items on the canvas, then right-click → **Stack** to combine them into a new deck-like stack. Stacks behave like decks and can be drawn from, shuffled, and searched.

To return a stack's cards to their original decks: right-click → **Disband Stack**.

### Deck Search / Card Picker

Right-click a deck or stack → **Search / Browse** to open the Card Picker. From here you can:

- **Search** cards by name
- **Drag rows** to reorder the deck
- **Split** the deck at the selected card (cards above go into a new stack)
- **Reset Order** — restore alphabetical order
- **Shuffle** — randomise the deck
- Adjust **thumbnail size** with the slider

---

## Dice

### Opening the Dice Bag

Press `B` or use the Tools menu to open the **Dice Bag**. Select a die type and click **Add to Canvas**.

Available dice: d4, d6, d8, d10, d12, d20, dF (Fate/Fudge)

### Rolling Dice

| Action | Result |
|---|---|
| `R` | Roll all selected dice |
| Double-click die | Roll it |
| Right-click die | Context menu |

Dice display their result and animate when rolled. Roll history is available in the **Roll Log** (accessible from the right-click context menu).

---

## Images

### Adding Images

**From the Image Library** (`I` key): browse and place previously imported images.

**Drag and drop**: drag an image file from Windows Explorer onto the canvas.

**Paste from clipboard** (`Ctrl+V`): paste any image copied from a browser, image editor, or file. The image is automatically saved to your local Images folder.

### Image Library

The Image Library (`I`) manages your image collection:

- **Scene tab** — images currently on the canvas
- **Library tab** — all locally saved images

From the Library tab you can:
- **Spawn** an image onto the canvas
- **Rename** an image (right-click → Rename)
- **Delete** an image (with confirmation; warns if in use on canvas)
- **Localize** linked images (copies them into your local folder)
- **Create folders** and **move images** between folders for organisation

---

## Notepad

Press `N` or use the Tools menu to open the **Notepad**.

The Notepad is a WYSIWYG Markdown editor. Files are saved as `.md` and rendered as rich text.

### File Menu

| Action | Description |
|---|---|
| New | Start a blank untitled note |
| Open | Open any `.md`, `.html`, or `.txt` file |
| Save | Save the current file (or prompt for location if untitled) |
| Save As | Save to a new location |

The last opened note is remembered and reloaded automatically.

### Formatting

| Button / Key | Format |
|---|---|
| **B** / Ctrl+B | Bold |
| *I* / Ctrl+I | Italic |
| U / Ctrl+U | Underline |
| H1 / Ctrl+1 | Heading 1 |
| H2 / Ctrl+2 | Heading 2 |
| H3 / Ctrl+3 | Heading 3 |

Headings are displayed larger, bold, and underlined (relative to your chosen font size). Clicking a heading button again on an already-formatted line removes the heading.

Use the **Font** and **Size** menus to choose a display font and size. These are display-only preferences — the underlying Markdown is not affected. Settings persist between sessions.

---

## Sessions

### Saving

- **File → Save** — saves to the current named session (or prompts for a name if unsaved)
- **File → Save As** — save under a new name
- Each save includes a **canvas screenshot** stored alongside the session file

### Loading

- **File → Open Session** — browse saved sessions with thumbnail previews
- Sessions can be deleted from the Open Session dialog (click the **✕** button, then confirm)

### Autosave

SoloCanvas autosaves when you close the window:
- If a named session is active, it saves to that session
- Otherwise it saves to a timestamped autosave file

### Startup

On launch, a dialog asks whether to **start a new session** or **load a saved one**.

---

## Settings & Hotkeys

Open **Settings** from the menu bar to configure:

- **Hotkeys** — rebind all keyboard shortcuts
- **Canvas** — background colour, grid style, grid size, snap-to-grid
- **Display** — zoom limits, hover preview, card sizes

### Default Hotkeys

| Key | Action |
|---|---|
| `1`–`9` | Draw cards from hovered deck to hand |
| `Shift`+`1`–`9` | Draw cards from hovered deck to canvas |
| `F` | Flip selected cards / decks |
| `R` | Roll selected dice / shuffle selected decks |
| `U` | Send selected items to back |
| `N` | Open Notepad |
| `D` | Open Deck Library |
| `I` | Open Image Library |
| `B` | Open Dice Bag |
| `Ctrl+V` | Paste image from clipboard |
| `Ctrl+1/2/3` | Apply H1/H2/H3 in Notepad |

---

## Folder Structure

```
SoloCanvas/
  main.py             ← entry point
  src/                ← application source
  Decks/              ← card decks (one subfolder per deck)
  Dice/               ← dice SVG assets (bundled)
  Images/             ← localised image library
  Notes/              ← notepad files
  launch.bat          ← Windows launch helper
  build.bat           ← Windows PyInstaller build script
  requirements.txt
```

User data (sessions, settings) is stored in `%APPDATA%\SoloCanvas\`.

---

## Screenshots

**Canvas & Notepad** Split screen with Foxit Reader, which is how I use it a lot.
![Canvas and Notepad](screenshots/notepad_canvas.png)

**Deck Search** — Browse and manage decks on the canvas.
![Deck Search Dialog](screenshots/deck_search.png)

**Dice Bag & Roll Log** — Add custom dice to the canvas, make new sets, access Roll Log.
![Dice Bag and Roll Log](screenshots/dice_bag.png)

**Deck Library** — The deck subfolder turn into decks and are accessed in your Deck Library
![Deck Library Dialog](screenshots/deck_library.png)

**Open Session** — Open a saved session, or the autosave if you didn't save it on your own.
![Open Session Dialog](screenshots/open_session.png)

---

## License

SoloCanvas is free software, distributed under the **GNU General Public License v3.0**.

Copyright © 2026 Geoffrey Osterberg

You may redistribute and/or modify it under the terms of the GPL as published by the Free Software Foundation — either version 3 of the License, or (at your option) any later version.

See [LICENSE](LICENSE) or <https://www.gnu.org/licenses/> for the full text.
