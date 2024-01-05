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
 * Yield to the next game logic routine.
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
 * Convenience function for setting room layout and collision.
 *
 * @param layout Room layout to use.
 */
inline void SetupRoom(RoomLayout *layout) {
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
inline void ShowMessage(int32_t messageId) {
    Game.messageId = messageId;
    Game.flags040 |= STATE_SHOW_MESSAGE;
}

#ifdef __cplusplus
}
#endif