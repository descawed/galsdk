# galsdk
Editor and utilities for the PSX game Galerians (1999). Requires Python 3.11.

## Editor
The editor is a GUI application for exploring the game's files. Run it from the repo's root directory with
`python -m galsdk.editor`. "Editor" is currently a bit of a misnomer because it lacks the ability to save changes
(although that is planned for the future), so it's mainly a viewer. It's a bit janky, but it has a few useful features.

### Projects
A project is a folder where the editor extracts game files and their metadata. Before you can view anything in the
editor, you need to create a project by using File > New Project (or ctrl-N) and selecting a CD image to extract.
The image should be in BIN/CUE format (although any CUE file is actually ignored). Currently, only the US and Japanese
retail versions of the game are supported. Support for demos and European versions is planned for the future.

After selecting the appropriate BIN image, the GUI will display some information about the version of the game it
contains. Choose a directory for the project to be created in with the Browse button and then click Create Project. Wait
a minute for it to finish extracting the game files and you'll be taken to the project view.

To open an existing project, use File > Open Project (or ctrl-O) and select the project directory.

### Tabs
- **Room** - This is probably the most useful feature of the editor. From this tab, you can view the layout of all the
    rooms in each of the game's 4 stages. When first clicking on a room, you will be shown an overhead view of the
    floor layout. A room consists of a few different types of objects which are listed below. You can right-click on the
    category name within the room to show an option to toggle display of that type of object on or off. Clicking on an
    object will highlight it in the 3D view.
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
  - **Cameras** - Cameras define the different camera angles the room can be viewed from in-game. Each camera angle is
    associated with a particular pre-rendered background image. Cameras' 3D positions are represented in the 3D view by
    a model of a film camera (although those models currently don't point the right way). You can click on a camera
    angle in the list to view the room from that camera angle with the associated background. The orientation and scale
    settings on the camera are not currently reflected by the 3D view.
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
    then call the "Callback" function to perform the action associated with the trigger. The final important piece of
    information attached to triggers is the actor flags. If one of the actor flags is set, the trigger area bounds are
    ignored and the trigger will instead fire when the player activates/scans/etc. the flagged actor. The trigger will
    only fire if the actor is dead unless the "Allow living actor" flag is set. Note that there is no flag for Actor 0
    because Actor 0 is always the player.
- **String** - This tab shows the game's message strings. "Messages" exclusively means the messages that appear at the
  bottom of the screen, e.g. when inspecting objects; all other text consists of standalone images. Each stage of the
  game has a separate message file, so this tab groups messages by stage. Some versions of the game also include
  additional debug strings which will show as a group called "Unmapped". When clicking on a string, you will be shown an
  image of that string rendered in the game font as well as a text box to edit the string. There are various control
  codes that can be used depending on the version of the game.
  - The English (and presumably other non-Japanese) versions of the game use control codes prefixed with $. The
    available codes are as follows:
    - $c(n) - Change text color. n is the index of the CLUT to use in the font TIM file. Valid indexes are 0 (white),
      1 (red), and 4 (yellow).
    - $r - New line. Erases the currently displayed text before showing the next line.
    - $w - Wait for the user to press the activate button before continuing.
    - $y - Display a yes/no prompt.
    - $p(n) - Wait until the game fires event number n before continuing.
    - $l - Probably either left-align or "carriage return" (return to beginning of line). Seems buggy. Never used.
    - $$ - A literal dollar sign.
  - The Japanese version of the game is more complicated. The game uses two font images - a basic image consisting of
    common characters (digits, punctuation, latin characters, and kana) and a second image consisting of kanji
    characters which differs from stage to stage. The strings don't use a common encoding (e.g. Shift-JIS or UTF-8) but
    are just a series of indexes into the two font images. This has a couple implications. The first is that I only have
    a transcription of the kanji used by Stage A, so when viewing strings for the other stages, the text box will just
    contain the character code in angle brackets (e.g. \<2054>) instead of the actual character. If anyone feels like
    transcribing the kanji for the other three stages, I would appreciate it! The second implication is that, on any
    given stage, you can only use kanji that are present in that stage's kanji image. With that out of the way, we can
    discuss control codes. Control codes and their arguments are represented by numbers in angle brackets just like
    unknown characters. They are as follows:
    - \<32769> - New line. Erases the currently displayed text before showing the next line.
    - \<32770> - Wait for the user to press the activate button before continuing.
    - \<32771>\<n> - Wait until the game fires event number n before continuing.
    - \<32772> - Erases the currently displayed text and left-aligns the next message. This appears to be a working
      equivalent of the English version's $l code.
    - \<32773> - Display a yes/no prompt.
    - \<32774>\<n> - Change text color. n is the index of the CLUT to use in the font TIM file. Valid indexes are 0
      (white), 1 (red), and 4 (yellow).
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
- **Background** - This tab shows the background images associated with each stage of the game. Each entry in the list
  contains one or more images. The first image is always the background image itself. Subsequent images are overlaid
  in front of the background depending on their 3D position defined by the camera angle being viewed. These are mainly
  used for objects in the background that should appear in front of the player when you walk behind them, but also for
  things like lights that change color when you activate something or items that disappear after you pick them up.
  You can right-click on an image in the list to export.
- **Item** - This tab displays the inventory icons and 3D models associated with each item in the game. When clicking
  on an item, the item's model will be displayed in the 3D view, its inventory description will appear in the bottom
  left, and its inventory icon will appear in the bottom right. Items are divided into key items and medicine (i.e.
  consumables). Medicine items do not have 3D models.
- **Model** - This tab allows viewing of all the games 3D models. This includes actor and item models that are visible
  on previous tabs, as well as "Other" models which are either unused or appear as movable objects in the game world.
  You can right-click on a model in the list to export. See the documentation for the Actor tab for details on how
  animations work on this tab and how they affect exporting.
- **Art** - This tab allows viewing and exporting of all known images in the game except for backgrounds and model
  textures (which are available on other tabs). The exact organization of images on this tab varies depending on your
  game version. You can right-click on an image in the list to export.
- **Menu** - This tab displays images defined in menu files. These files don't exist in the Japanese version, so this
  tab won't appear for Japan-version projects. The other versions have two menu files, one for the option menu and
  one for the inventory. In addition to displaying the icons within each menu, the top-level entry for the option menu
  can also display a preview of the full menu rendered together. This is not currently supported for the inventory menu.
  You can right-click on an image in the list to export.
- **Movie** - On this tab you can view the game's FMVs. There's no export option in the UI, but if you watch a video
  in the editor, you can find a copy of it in .avi format in \<project dir>/stages/\<stage letter>/movies. Which stage's
  FMVs are available to view depends on which disc you created the project from, although you can manually copy the
  FMVs from other discs into the appropriate directory in the project if you want to have them all available.
- **Voice** - This tab allows you to listen to the game's spoken dialogue. Like the Movie tab, there is no export option
  in the UI, but playing a voice recording will create a copy in .wav format in \<project dir>/voice.

## CLI utilities
galsdk also comes with a number of CLI tools for manipulating the game's files. Since the editor is currently read-only,
these are what you want if you actually want to make changes to the game. Each tool can be run with
`python -m <module name>` and has usage help available with the `-h` option. The following modules have CLI interfaces:
- `galsdk.animation` - Pack and unpack animation databases from MOT.CDB. You usually want to use the `--all` switch when
  unpacking, because animation databases can have gaps. `--all` exports empty files for animations that aren't present.
  Without these empty files, the animations will likely be in the wrong order when repacked.
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
  the various dialogue recordings for  discs 1, 2, and 3 respectively. Run this tool with the path to the file from
  DISPLAY.CDB for the disc you want, followed by the path to the XA file, and finally the path to a directory to extract
  the recordings to. This tool doesn't currently work with the Japanese version because the XA layouts are hard-coded
  in the exe.
- `psx.cd` - Patch updated files into a BIN CD image. After you make changes to game files, you can use this to replace
  the old versions of the files on the CD. You should try to make sure the size of the changed file is the same as (or
  possibly less than) the original file. The tool tries to handle shuffling things around if the size changes, but it
  doesn't really work.
- `psx.tim` - Convert TIM images to other formats.