# FIFA 17 Player Editor

A small desktop editor for the player database of **FIFA 17** (PC). It's written in Python 3
with Tkinter and needs no extra packages. Edit players, create new ones, and change their
appearance, then load the result into the game as a Frosty mod.

There is problably better tools to do the same outcome but i wanted my own. 

```
python3 editor.py                         # reopens your last project, or File ▸ Open database…
python3 editor.py path/to/fifa_ng_db.DB   # the *-meta.XML next to it is found automatically
```

## What it does

- **Edit players:** ratings, positions, foot, skills, work rates, traits, nationality, club,
  shirt number, contract, and every raw field.
- **Create players:** clone a template player and give them a new name, club and number. New
  players get a generic face.
- **Work in Progress Appearance tab:** face, hair, beard, body, accessories, boots and kit style. ◀ ▶ step
  (Still working on this) You can also copy a look from another player, or generate a random
  generic look.
- **Customise in-game:** marks a created player as editable inside FIFA 17, so you can change
  their look with the game's own tools.
- **Project folders:** Save puts the database, its schema, language files and a list of
  everything you created into one folder. The editor reopens it on start and highlights your
  players (green = created, yellow = edited).
- **Safe saving:** checksums are recalculated, and your original export is never
  overwritten.
  
  
  ## Workflow: changing players (i will add images later so the workflow is more simple to understand)

1. **Export the database.** In Frosty Editor, open the Legacy Explorer, go to `data/db/`, and
   export `fifa_ng_db.db` and `fifa_ng_db-meta.xml` into one folder.
2. **Edit.** Run `python3 editor.py`, open `fifa_ng_db.DB`, and pick a player from the list.
   Change ratings and the other tabs, or use **Edit ▸ New player…** (tick *Customise in-game*
   if you want to finish the look inside FIFA).
3. **Save** (Ctrl+S). The first save creates `fifa_ng_db project/` next to the file. Later
   saves go into that folder.
4. **Import.** In Frosty Editor, import `fifa_ng_db project/fifa_ng_db.DB` over
   **`data/db/fifa_ng_db.db`**. Use exactly that slot; Then save the project and export it as a `.fbmod`.
5. **Play.** Enable the mod in Frosty Mod Manager, launch, and check your players. To customise
   a created player's look in-game, use FIFA's Customise ▸ Edit Teams ▸ Edit Player.
6. **Come back later.** Starting the editor reopens your project, and your players are listed
   in green/yellow ("Mine only" filters to them).

Always keep a copy of your original export. If the game rejects a database, check
**Help ▸ Database info**. It shows the file, the schema and the Frosty slot to import over.


## What it can't do

- **No real (scanned) faces for new players.** Those faces live in the game's own asset
  bundles. Copying a look gives a new player the generic codes only.
- **No image previews** of hair, boots or accessories. The game doesn't document what the
  codes mean, so the editor shows example players instead.
- **Overall rating isn't recalculated** from attributes. Set it yourself.
- **Creating teams is on hold** and marked experimental. New teams can show missing kits or
  break career mode.
- It doesn't patch the game directly. You import the edited database with
  [Frosty Mod Manager / Editor](https://github.com/CadeEvs/FrostyToolsuite).
- It's only tested with FIFA 17 on PC, using `fifa_ng_db` (main database) and `fifa_si_db`.


## Files

- `editor.py`: the GUI.
- `fifadb.py`: the FIFA database reader/writer, with no GUI code.
- `crests.py`: crest helpers for teams.
- `tools/`: helpers for Frosty projects and test databases.

## Legal

- This is an unofficial fan project. It is **not affiliated with, endorsed by, or sponsored
  by Electronic Arts Inc., EA Sports or FIFA**. "EA SPORTS", "FIFA" and related names and
  logos are trademarks of their respective owners, used here only to describe what the
  software works with.
- This repository contains **no game files**: no databases, schemas, textures or other EA
  content. You need your own legitimately obtained copy of FIFA 17, and you work only on
  files exported from it.
- Player names, likenesses and club data in the game's database belong to their respective
  rights holders. **Don't redistribute** databases, language files or mods that contain them
  unless you have the right to.
- Meant for **offline, single-player** use. Don't use modified files online or anywhere
  they could give an unfair advantage or break a service's terms.
- Provided **"as is", without warranty of any kind**. You use it at your own risk. The authors
  aren't liable for damaged saves, game installs or data. Back up your files.
- Frosty Toolsuite is a separate project with its own license.
