#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <galerians/types.h>
#include <galerians/globals.h>

/**
 * Set the layout of the current room.
 *
 * @param game Pointer to the game state object.
 * @param colliders Receives the length of and pointer to the colliders array.
 * @param layout Room layout to use.
 */
void SetRoomLayout(GameState *game, ColliderArray *colliders, RoomLayout *layout);
/**
 * Set collision objects for the current room.
 *
 * @param numColliders Number of collision objects.
 * @param colliders Pointer to array of collision objects.
 */
void SetCollision(uint32_t numColliders, Collider *colliders);
/**
 * Setup active actors based on the provided actor layout.
 *
 * @param layout Actor layout to use.
 */
void SetupActors(ActorLayout *layout);
/**
 * Load a file from a database file.
 *
 * @param db The database to load from.
 * @param index The index of the file in the database to load.
 * @param buffer Pointer to the buffer to load the file to. If NULL, the buffer will be allocated dynamically.
 * @return Pointer to the buffer where the file data was loaded.
 */
void *LoadFileFromDb(Database *db, uint32_t index, void *buffer);
/**
 * Get the value (0 or 1) of a state flag for the current stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to get.
 * @return Value of the flag.
 */
int32_t GetStateFlag(GameState *game, int16_t flag);
/**
 * Set a state flag to true (1) for the current stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to set.
 */
void SetStateFlag(GameState *game, int16_t flag);
/**
 * Clear (set to false/0) a state flag for the current stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to clear.
 */
void ClearStateFlag(GameState *game, int16_t flag);
/**
 * Get the value (0 or 1) of a state flag for the given stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to get.
 * @param stage Stage to check the flag for.
 */
int32_t GetStageStateFlag(GameState *game, int16_t flag, int16_t stage);
/**
 * Set a state flag to true (1) for the given stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to set.
 * @param stage Stage to set the flag for.
 */
void SetStageStateFlag(GameState *game, int16_t flag, int16_t stage);
/**
 * Clear (set to false/0) a state flag for the given stage.
 *
 * @param game Pointer to the game state object.
 * @param flag Index of the flag to clear.
 * @param stage Stage to clear the flag for.
 */
void ClearStageStateFlag(GameState *game, int16_t flag, int16_t stage);
/**
 * Yield to the next game task.
 *
 * This function will return on the next frame.
 */
void Yield();
/**
 * Leave the current room and go to the specified room.
 *
 * @param game Pointer to the game state object.
 * @param mapId ID of the map which the target room is in.
 * @param roomId Index in the map of the target room.
 * @param doorSoundId Door sound to play when transitioning to the room.
 */
void GoToRoom(GameState *game, int16_t mapId, int16_t roomId, int32_t doorSoundId);
/**
 * Transition from the current stage to the specified stage.
 *
 * @param game Pointer to the game state object.
 * @param stage ID of the stage to change to.
 */
void ChangeStage(GameState *game, int16_t stage);
/**
 * Pick up a key item.
 *
 * @param game Pointer to the game state object.
 * @param itemId ID of the item to pick up.
 * @param messageId ID of the message to show when picking up the item.
 * @param flags Flags to control the pickup animation.
 * @param pickup Position and sound settings for the pickup animation.
 * @return Success.
 */
int32_t PickUpKeyItem(GameState *game, int32_t itemId, int32_t messageId, uint16_t flags, PickupAnimation *pickup);
/**
 * Add an item directly to the player's inventory with no notification.
 *
 * @param game Pointer to the game state object.
 * @param itemId ID of the item to add to the player's inventory.
 */
void AddItemToInventory(GameState *game, int32_t itemId);
/**
 * Pick up a file item.
 *
 * @param unknown Always 9. Seems to be an index into an OTag list.
 * @param itemId ID of the item to pick up.
 */
void PickUpFile(int32_t unknown, int32_t itemId);
/**
 * Show a scan image (i.e. one of the images from ITEMTIM.CDB).
 *
 * @param game Pointer to the game state object.
 * @param timIndex Index of the TIM in ITEMTIM.CDB.
 */
void ShowItemTim(GameState *game, int32_t timIndex);
/**
 * Play an STR movie.
 *
 * @param game Pointer to the game state object.
 * @param movieIndex Index of the movie in the internal movie list.
 * @param useDelay If non-zero, wait for 9 frames before starting the video. Otherwise, the wait will be 1 or more frames
 *                 depending on an unknown value configured elsewhere.
 * @param postAction Select an action to be performed after the video completes. 0 = something involving (re-?)loading
 *                   the models of all actors in the room; not entirely clear. 1 = restore the previous camera angle?
 *                   2 = no action.
 */
void PlayMovie(GameState *game, int32_t movieIndex, int16_t useDelay, int16_t postAction);

// Module types
#define MODULE_TYPE_ROOM    0
#define MODULE_TYPE_AI      1
// as the one exception, the main menu is also a type 1 module
#ifdef GALERIANS_REGION_JAPAN
#define MODULE_TYPE_HEALTH  2
#define MODULE_TYPE_CREDITS 3
#define MODULE_TYPE_SAVE    4
#else
#define MODULE_TYPE_CREDITS 2
#define MODULE_TYPE_SAVE    3
#endif

#ifdef GALERIANS_REGION_JAPAN
/**
 * Load a module.
 *
 * @param type Type of the module to be loaded.
 * @param index Index in MODULE.BIN of the module to be loaded.
 * @param loadAddress Address in memory at which to load the module. Typically, this should be ModuleLoadAddresses[type].
 */
void LoadModule(int16_t type, int16_t index, void *loadAddress);
#else
/**
 * Load a module.
 *
 * @param type Type of the module to be loaded.
 * @param index Index in MODULE.BIN of the module to be loaded.
 */
void LoadModule(int16_t type, int16_t index);
#endif
/**
 * Load an AI (type 1) module.
 *
 * @param index Index in MODULE.BIN of the AI module to be loaded.
 */
void LoadAiModule(int16_t index);
/**
 * Set an actor's AI routine.
 *
 * @param actor Actor whose AI routine to set.
 * @param aiRoutine AI routine.
 */
void SetActorAiRoutine(Actor *actor, AiRoutine aiRoutine);
/**
 * Did the player select "Yes" on the last yes/no prompt?
 *
 * @return Whether the player selected "Yes".
 */
int16_t PlayerSelectedYes();

/**
 * Convenience function for loading a module at the standard address in any region.
 *
 * @param type Type of the module to be loaded.
 * @param index Index in MODULE.BIN of the module to be loaded.
 */
static inline void LoadModuleStd(int16_t type, int16_t index) {
    LoadModule(
        type,
        index
        #ifdef GALERIANS_REGION_JAPAN
        , ModuleLoadAddresses[type]
        #endif
    );
}

/**
 * Convenience function for setting room layout and collision.
 *
 * @param layout Room layout to use.
 */
static inline void SetupRoom(RoomLayout *layout) {
    ColliderArray colliders;

    SetRoomLayout(&Game, &colliders, layout);
    SetCollision(colliders.numColliders, colliders.colliders);
}

/**
 * Show a message at the bottom of the screen.
 *
 * @param messageId ID of the message to show. In the Japanese version, this is the byte offset in the message file. In
 *                  other versions, this is the index in the message file.
 */
static inline void ShowMessage(int32_t messageId) {
    Game.messageId = messageId;
    Game.flags040 |= STATE_SHOW_MESSAGE;
}

/**
 * Show a message and wait for it to complete.
 *
 * Note that completion requires the player to press a button to dismiss the message if the message contains the $w code.
 * @param messageId ID of the message to show. In the Japanese version, this is the byte offset in the message file. In
 *                  other versions, this is the index in the message file.
 * @return Whether the player selected "Yes". This return value is only meaningful for messages that contain the $y code.
 */
static inline int16_t WaitForMessage(int32_t messageId) {
    ShowMessage(messageId);

    // wait for message to be displayed
    while ((Game.flags03C & STATE_DISPLAYING_MESSAGE) == 0)
        Yield();

    // wait for message to complete
    while (Game.flags03C & STATE_DISPLAYING_MESSAGE)
        Yield();

    // return whether the player selected yes or no
    return PlayerSelectedYes();
}

#ifdef __cplusplus
}
#endif