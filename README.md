# galsdk
Editor and utilities for the PSX game Galerians (1999). Requires Python 3.12 or 3.13.

## Setup
Packaged releases for Windows are available on the [Releases](https://github.com/descawed/galsdk/releases) tab.
Mac and Linux users, or those who want the latest changes, will need to clone the repo and run the scripts with Python
directly. For those familiar with Python, the easiest way to use this application is with [Poetry](https://python-poetry.org/).
If you're less familiar with Python, or just don't want to use Poetry, you can use the following instructions to set up
a Python virtual environment:

1. Install [Python 3.12](https://www.python.org/downloads/) if you don't have it.
2. Clone down the repo: `git clone https://github.com/descawed/galsdk.git`
3. cd to the repo directory: `cd /path/to/galsdk`.
4. Create the virtual environment: `python -m venv ./venv`.
5. Enter the virtual environment. Windows: `.\venv\Scripts\activate.bat`. Mac/Nix: `source ./venv/bin/activate`.
6. Install dependencies: `python -m pip install -r requirements.txt`.
7. Run desired commands as described below (e.g. `python -m galsdk.editor`).
8. When you're done, exit the virtual environment with the command `deactivate`.
9. Next time you want to use the tools, remember to enter the virtual environment first as in step 5.

## SDK
The SDK is a set of C headers and linker scripts for building your own modules. Modules are loadable binaries that
implement the game's rooms, AI, and certain menus. See the README in the sdk directory for details. The tutorial for
building the sample room also provides some examples of how to use the editor.

## Editor
The editor is a GUI application for exploring the game's files. If you're using a packaged release, run `editor.exe`.
Others can run it from the repo's root directory with `python -m galsdk.editor`. At the moment, it supports editing
rooms, strings, art textures, and some animation data. Support for editing other files will be added in the future.

The editor supports Windows and Linux. Unfortunately, it doesn't work on Mac at the moment. I hope to correct this at
some point. CLI tools should still work on Mac.

### Projects
A project is a folder where the editor extracts game files and their metadata. Before you can view anything in the
editor, you need to create a project by using File > New Project (or ctrl-N) and selecting a CD image to extract.
The image should be in BIN/CUE format (although any CUE file is actually ignored). Currently, all retail versions of the
game except for the French version are supported. Support for demos and the French version is planned for the future.

After selecting the appropriate BIN image, the GUI will display some information about the version of the game it
contains. Choose a directory for the project to be created in with the Browse button and then click Create Project. Wait
a minute for it to finish extracting the game files and you'll be taken to the project view.

To open an existing project, use File > Open Project (or ctrl-O) and select the project directory. To export your
changes to a playable CD image, use File > Export (make sure to save first). Not all files can be edited within the
editor at this time, but if you make changes to project files outside the editor, the export process will still pick
them up based on the file modification timestamps.

### Tabs
- **Room** - This is probably the most useful feature of the editor. From this tab, you can view the layout of all the
    rooms in each of the game's 4 stages. When first clicking on a room, you will be shown an overhead view of the
    floor layout. A room consists of a few different types of objects which are listed below. You can right-click on the
    category name within the room to show an option to toggle display of that type of object on or off. Clicking on an
    object will highlight it in the 3D view. You can also select objects by clicking on them in the 3D view. Clicking on
    a camera will show the view from that camera, with the camera's target point displayed as an X. Finally, you can
    click and drag selected objects to move or resize them (although it's a bit janky at the moment). Beyond the room
    viewer, you can also click the "Edit maps" button at the bottom of the window to view and edit how rooms are
    assigned to maps. This also allows you to import custom room modules you've created.
  - **Actors** - This shows the actors (characters) present in the room. Rooms may have multiple actor layouts for
    different scenarios, although most only have one. The game has a hard-coded limit of four actors per room, the first
    of which is always the player. Therefore, each layout has a fixed list of four actor slots, although slots may be
    unused if the room contains fewer than the maximum of four. Each actor instance placed in the game has an ID which
    I believe is used for tracking which enemies have been killed. IDs are usually unique, but NPCs who can't be killed
    sometimes have the same ID. Clicking on a different layout will update the 3D view to show the actors from that
    layout.
  - **Colliders** - Colliders are solid obstacles that obstruct the player's movement. The first collider is always the
    room's walls, shown in red in the 3D view. This defines the playable area which the player cannot exit. Other
    colliders are shown in green and represent obstacles within the room. The game supports rectangular, triangular, and
    circular colliders. Wall-type colliders are rectangular but inverted such that the player is blocked from walking
    out of the area rather than walking into it.
  - **Entrances** - Entrances are the different points the player can appear at when entering a room. Typically, you
    enter a room by going through a door, and the entrance point corresponds to where you appear on the other side of
    the door. There are also a few scripted entrance points, though, such as where you start at the beginning of each
    stage. Entrances appear in the 3D view as cones pointing in the direction the player will face when entering at
    that point.
  - **Cameras** - Cameras define the different camera angles the room can be viewed from in-game. Each camera angle is
    associated with a particular pre-rendered background image. Cameras' 3D positions are represented in the 3D view by
    a model of a film camera. You can click on a camera angle in the list to view the room from that camera angle with
    the associated background. The orientation and scale settings on the camera are not currently reflected by the 3D
    view.
  - **Cuts** - Cuts define which camera angle the game should use when the player is standing in various parts of the
    room. Cuts are shown in orange in the 3D view. When the player moves from one cut to another, the camera angle will
    change to the one defined by the cut.
  - **Triggers** - Triggers are areas in the room that can be interacted with or that trigger an event when the player
    walks into them. These include things like doors, item pickups, and scannable objects. Each trigger has an
    associated condition that determines under what circumstances the trigger will fire, such as when the player presses
    the activate button or the scan button. Note that there are a few scanning-related conditions that are not used in
    the final game; these appear to be related to a cut feature where it would have been possible to combine scanning
    with an item. If the player enters the trigger area and fulfills the associated condition, the game will call the
    "Enabled" callback (if present) to determine if the trigger is enabled. If the trigger is enabled, the game will
    then call the "Callback" function to perform the action associated with the trigger. If either callback contains
    calls to any common game functions, such as checking a flag or picking up an item, those will be shown in an
    "Actions" box below the callback. There you can modify the arguments, or disable the call by unchecking the box next
    to its name. The final important piece of information attached to triggers is the actor flags. If one of the actor
    flags is set, the trigger area bounds are ignored and the trigger will instead fire when the player
    activates/scans/etc. the flagged actor. The trigger will only fire if the actor is dead unless the "Allow living
    actor" flag is set. Note that there is no flag for Actor 0 because Actor 0 is always the player.
- **String** - This tab shows the game's message strings. "Messages" exclusively means the messages that appear at the
  bottom of the screen, e.g. when inspecting objects; all other text consists of standalone images. Each stage of the
  game has a separate message file, so this tab groups messages by stage. There also additional debug strings that go in
  their own group. When clicking on a string, you will be shown an image of that string rendered in the game font as
  well as a text box to edit the string. There are various control codes that can be used depending on the version of
  the game.
  - The English (and presumably other non-Japanese) versions of the game use control codes prefixed with $. The
    available codes are as follows:
    - $c(n) - Change text color. n is the index of the CLUT to use in the font TIM file. Valid indexes are 0 (white),
      1 (red), and 4 (yellow).
    - $r - New line. Erases the currently displayed text before showing the next line.
    - $w - Wait for the user to press the activate button before continuing.
    - $y - Display a yes/no prompt.
    - $p(n) - Wait until the game fires event number n before continuing.
    - $l - Probably left-align. Seems buggy. Never used.
    - $$ - A literal dollar sign.
  - The Japanese version of the game is more complicated. The message format is binary, but the editor will display
    control codes in the \$ format above for consistency. The game uses two font images - a basic image consisting of
    common characters (digits, punctuation, latin characters, and kana) and a second image consisting of kanji
    characters which differs from stage to stage. The strings don't use a common encoding (e.g. Shift-JIS or UTF-8) but
    are just a series of indexes into the two font images. This has a couple implications. The first is that I only have
    a transcription of the kanji used by Stage A, so when viewing strings for the other stages, kanji characters will
    display as a \$k code followed by the kanji index (e.g. \$k(26)). If anyone feels like transcribing the kanji for the
    other three stages, I would appreciate it! The second implication is that, on any given stage, you can only use
    kanji that are present in that stage's kanji image.
    
    With that out of the way, we can discuss control codes. The same set of control codes from the other versions are
    supported, and the \$l code seems to work properly in this version. In addition to the \$k code used for unknown
    kanji, the editor also supports a \$u code which can be used for unknown values in the message data, e.g. \$u(1234).
    
    The last caveat is that the Japanese version of the game references strings by their offset in the file rather than
    by index like the Western versions do. This means that if you change the length of a string, you'll break every
    string that comes after it in that group. If you want to make the string shorter, you can try padding back to the
    original length with spaces and/or color control codes, which take up no space and will be invisible if no text
    comes after them. If you want to make it longer, there's no option but to patch the game code with the updated
    offsets.
- **Actor** - This tab allows you to view the 3D model for each actor in the game. The number preceding the actor name
  in the list is the actor ID. Note that this is not the same ID shown in the actor section of the Room tab, which
  identifies a specific placed *instance* of an actor. All of these models are also viewable on the Model tab. The
  difference with this tab is that some actors in the game are defined to use the same model (for instance, Rion's
  mirror image uses the same model as the playable Rion actor). The model tab will only show each model once, but this
  tab has distinct entries for actors that share a model, and shows their unique IDs next to their name. You can also
  have the actor play an animation by selecting an animation set and animation at the bottom of the screen. Each actor
  has a default animation set with common animations like idle, walking, running, etc., but you can (attempt to) play
  any animation on any actor. Finally, you can right-click on an actor in the list for an option to export the model
  and/or texture. When exporting to glTF or GLB, the currently selected animation set will also be included in the
  export.
- **Animation** - This tab allows you to view and edit character animations. The game contains multiple animation
  "databases", each of which contains zero or more animations. Animation databases that are associated with a particular
  character will show that character's name. The remaining databases generally contain animations for cutscenes or
  player-specific actions. Each animation contains a list of attack data, which is used for melee attacks, and multiple
  animation frames. You can edit the flags and translation for each frame. Rotation editing is not currently supported.
  If you right-click on animation in the list, you can delete it or copy another animation in its place. If you
  right-click on an animation database, you can choose to copy all animations from another database over the animations
  of this database, or to copy only animations that are missing in this database.
- **Item** - This tab displays the inventory icons and 3D models associated with each item in the game. When clicking
  on an item, the item's model will be displayed in the 3D view, its inventory description will appear in the bottom
  left, and its inventory icon will appear in the bottom right. Items are divided into key items and medicine (i.e.
  consumables). Medicine items do not have 3D models.
- **Model** - This tab allows viewing of all the games 3D models. This includes actor and item models that are visible
  on previous tabs, as well as "Other" models which are either unused or appear as movable objects in the game world.
  You can right-click on a model in the list to export. See the documentation for the Actor tab for details on how
  animations work on this tab and how they affect exporting.
- **Art** - This tab allows viewing and exporting of all known images in the game except for model textures (which are
  available on other tabs). The exact organization of images on this tab varies depending on your game version. You can
  right-click on an image in the list to export, or to import a replacement image. You can import any common image
  format and it will be converted to TIM automatically, but only a single CLUT is supported. If you need multiple
  palettes, use a tool like [TIMedit](https://github.com/Lameguy64/TIMedit) to create a TIM with the appropriate structure and import that.
- **Menu** - This tab displays images defined in menu files. These files don't exist in the Japanese version, so this
  tab won't appear for Japan-version projects. The other versions have two menu files, one for the option menu and
  one for the inventory. In addition to displaying the icons within each menu, the top-level entry for the option menu
  can also display a preview of the full menu rendered together. This is not currently supported for the inventory menu.
  You can right-click on an image in the list to export.
- **Movie** - On this tab you can view the game's FMVs. There's no export option in the UI, but if you watch a video
  in the editor, you can find a copy of it in .avi (Windows) or .mp4 (other platforms) format in
  \<project dir>/stages/\<stage letter>/movies. Which stage's FMVs are available to view depends on which disc you
  created the project from, although you can manually copy the FMVs from other discs into the appropriate directory in
  the project if you want to have them all available.
- **Voice** - This tab allows you to listen to the game's spoken dialogue. Like the Movie tab, there is no export option
  in the UI, but playing a voice recording will create a copy in .wav format in \<project dir>/voice.

## CLI utilities
galsdk also comes with a number of CLI tools for manipulating the game's files. Each tool can be run with
`python -m <module name>` and has usage help available with the `-h` option. There are also a couple bonus scripts for
working with Galerians: Ash files (no additional Ash support is planned at this time). If you're using a packaged
release, there are .exe files corresponding to each of these modules with the prefix removed (e.g., the .exe
corresponding to `galsdk.animation` is `animation.exe`). The exception is the Galerians: Ash scripts, which start with
`ash_`, so `ash_bd.exe` and `ash_tex.exe`.

The following modules have CLI interfaces:
- `galsdk.animation` - Pack and unpack animation databases from MOT.CDB. You usually want to use the `--all` switch when
  unpacking, because animation databases can have gaps. `--all` exports empty files for animations that aren't present.
  Without these empty files, the animations will likely be in the wrong order when repacked.
- `galsdk.compress.dictionary` - Compress and decompress files using the game's dictionary compression algorithm. The
  game uses this for a number of TIM files. In most cases it's easier to use `galsdk.tim` to unpack and re-pack the TIM
  archives as that handles compression and decompression as well. Note that files produced by the compression process
  will generally not be identical to the original compressed files on the disc.
- `galsdk.db` - Pack and unpack .CDB files. Note that MODULE.BIN is also a CDB file, despite the extension.
- `galsdk.model` - Export the game's 3D models into other formats. To correctly export actor models, you need to know
  the actor ID (shown in the Actor tab of the editor or can be found in the actor list in galsdk/model.py). There is no
  import functionality at this time.
- `galsdk.module` - Dump room information. This is the same information available in the editor's Room tab but in text
  format. Note that not all modules in MODULE.BIN are room modules.
- `galsdk.sniff` - Auto-detect the format of game files. Can optionally rename the files with a suggested extension and
  export to another format (recursively if the file is an archive of some kind). This will correctly identify all but a
  few of the game's files in the versions I've tested so far.
- `galsdk.string` - Pack and unpack message files ("string databases"). This can also export messages as images rendered
  in the game's font, although you need an editor project for it to pull from. When working with Japanese strings, see
  the caveats listed above in the section on the editor's String tab.
- `galsdk.tim` - Pack and unpack "TIM databases". The game has many different formats for storing sequences of TIMs,
  some of which are compressed. When unpacking, the tool should be able to auto-detect the format. When packing, if you
  don't know the format you want, run the sniff tool on the original file and see what extension it suggests.
- `galsdk.vab` - Pack and unpack VAB databases that are found in SOUND.CDB. There are two different VAB database
  formats. When unpacking, the tool will auto-detect the format. When packing, if you don't know the format you want,
  run the sniff tool on the original file. If it suggests the .VDA extension, use the `--alternate` flag when packing.
- `galsdk.xa` - Unpack XA databases. The game's dialogue is stored in the disc's XA file(s) (XA.MXA in the US version,
  files in the XA directory in the Japanese version) with no indication where particular recordings begin or end. In the
  US version, DISPLAY.CDB entries 0, 1, and 2 are a kind of header-only database defining where in the XA file to find
  the various dialogue recordings for discs 1, 2, and 3 respectively. Run this tool with the path to the file from
  DISPLAY.CDB for the disc you want, followed by the path to the XA file, and finally the path to a directory to extract
  the recordings to. The unpack command doesn't work with the Japanese version because the XA layouts are hard-coded
  in the exe. However, you can use the mxa command to export Japanese audio in the Western XA.MXA format and then unpack
  that.
- `psx.cd` - Patch updated files into a BIN CD image. After you make changes to game files, you can use this to replace
  the old versions of the files on the CD. For best results, try to keep the size of the changed file less than or equal
  to the size of the original file. The tool tries to handle shuffling things around if a file gets bigger, but I'm not
  yet 100% confident in it. It can also extract files from the CD image.
- `psx.exe` - Apply binary patches to an EXE by address.
- `psx.tim` - Convert TIM images to other formats.
- `ash.bd` - Extract Galerians: Ash .BD1 and .BD2 archives.
- `ash.tex` - Convert Galerians: Ash texture images to other formats.