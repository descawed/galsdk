#include <stddef.h>
#include <galerians.h>

uint32_t module_id __attribute__ ((section ("MODULE_ID"))) = 0x8b;

RoomLayout layout = {
    .numColliders = 4,
    .colliders = {
        {
            .type = COLLIDER_WALL,
        },
        {
            .type = COLLIDER_RECT,
        },
        {
            .type = COLLIDER_CIRCLE,
        },
        {
            .type = COLLIDER_CIRCLE,
        },
    },
    .rectColliders = {
        {
            .xPos = 0,
            .zPos = 0,
            .xSize = 3623,
            .zSize = 3623,
            .unknown10 = 0xf,
        },
        {
            .xPos = 0,
            .zPos = 0,
            .xSize = 434,
            .zSize = 434,
            .unknown10 = 0xf,
        },
    },
    .circleColliders = {
        {
            .x = 217,
            .z = 3406,
            .radius = 217,
        },
        {
            .x = 3406,
            .z = 217,
            .radius = 217,
        },
    },
    .numCameras = 1,
    .cameras = {
        {
            .orientation = 0,
            .verticalFov = 600,
            .scale = 10,
            .x = 4294,
            .y = 1653,
            .z = 4196,
            .targetX = 2727,
            .targetY = 65,
            .targetZ = 2727,
        },
    },
    .cuts = {
        {
            .marker = 0,
            .index = 0,
            .x1 = 0,
            .z1 = 0,
            .x2 = 3623,
            .z2 = 0,
            .x3 = 0,
            .z3 = 3623,
            .x4 = 3623,
            .z4 = 3623,
        },
        {
            .marker = -1,
        },
    },
    .numInteractables = 3,
    .interactables = {
        {
            .id = 0,
            .xPos = 0,
            .zPos = 0,
            .xSize = 434,
            .zSize = 434,
        },
        {
            .id = 1,
            .xPos = 0,
            .zPos = 3189,
            .xSize = 434,
            .zSize = 434,
        },
        {
            .id = 2,
            .xPos = 3189,
            .zPos = 0,
            .xSize = 434,
            .zSize = 434,
        },
    },
};

ActorLayout actors = {
    .name = {'A', 'S', 'D', 'K', 'X', 0},
    .actors = {
        {
            .id = 1,
            .type = ACTOR_RION,
            .x = 1811,
            .y = 0,
            .z = 1811,
        },
        {
            .id = 32,
            .type = ACTOR_MECH_UNUSED,
            .x = 1811,
            .y = 0,
            .z = 1811,
        },
        { .type = ACTOR_NONE },
        { .type = ACTOR_NONE },
    },
};

// the first "mask" is the background image itself, whose fields are all zeroes
BackgroundMask masks[1];

Background background = {
    .index = 235,
    .numMasks = 1,
    .masks = masks,
};

void cubeTrigger(GameState* game) {
    static size_t fileItemIndex = 0;
    int32_t itemId;
    int32_t msgId;

    switch (fileItemIndex++) {
        case 0:
            ShowMessage(216);
            return;
        case 1:
            itemId = ITEM_MEDICAL_STAFF_NOTES;
            msgId = 45;
            break;
        case 2:
            itemId = ITEM_G_PROJECT_REPORT;
            msgId = 90;
            break;
        case 3:
            itemId = ITEM_PHOTO_OF_PARENTS;
            msgId = 46;
            break;
        case 4:
            itemId = ITEM_RIONS_TEST_DATA;
            msgId = 47;
            break;
        case 5:
            itemId = ITEM_DR_LEMS_NOTES;
            msgId = 48;
            break;
        case 6:
            itemId = ITEM_NEW_REPLICATIVE_COMPUTER_THEORY;
            msgId = 208; // copied from stage B
            break;
        case 7:
            itemId = ITEM_DR_PASCALLES_DIARY;
            msgId = 209; // copied from stage B
            break;
        case 8:
            itemId = ITEM_LETTER_FROM_ELSA;
            msgId = 210; // copied from stage B
            break;
        case 9:
            itemId = ITEM_NEWSPAPER;
            msgId = 169;
            break;
        case 10:
            itemId = ITEM_LETTER_FROM_LILIA;
            msgId = 211; // copied from stage C
            break;
        case 11:
            itemId = ITEM_UNUSED_0;
            msgId = 212;
            break;
        case 12:
            itemId = ITEM_UNUSED_7;
            msgId = 213;
            break;
        case 13:
            itemId = ITEM_UNUSED_10;
            msgId = 214;
            break;
        case 14:
            itemId = ITEM_UNUSED_18;
            msgId = 215;
            break;
        default:
            ShowMessage(172); // It's empty.$w
            return;
    }

    PickupAnimation pickupAnimation = {
        .soundSet = NULL,
        .soundId = 0,
        .voiceIndex = 0,
        .x = 300,
        .z = 520,
        .angle = 2048,
        .cameraId = 0
    };
    PickUpKeyItem(game, itemId, msgId, ITEM_PICKUP_RESTORE_CAMERA | ITEM_PICKUP_ANIM_STAND, &pickupAnimation);
}

void cylinderTrigger(GameState* game) {
    static int32_t timIndex = -1;

    if (timIndex++ < 0) {
        ShowMessage(217);
        return;
    }

    if (timIndex > 195)
        timIndex = 0;

    ShowItemTim(game, timIndex);
}

void sphereTrigger(GameState *game __attribute__((unused))) {
    if ((Actors[1].flags & ACTOR_FLAG_INVISIBLE) == 0) {
        if (WaitForMessage(219)) {
            /*
             * WARNING: we're referencing the Game global here instead of using the arg we already have to work around
             * a game bug. when the game calls into a task function, it sets the stack pointer to the first word BEFORE
             * the beginning of the stack instead of the first word on the stack. this is supposed to be part of the
             * argument register save area, so gcc may try to save the value of our argument there. in practice, this
             * usually doesn't cause any problems, UNLESS we Yield (like WaitForMessage does). when we resume from the
             * Yield, the saved argument on the stack will have been clobbered, and any subsequent references to it will
             * be invalid.
             */
            PlayMovie(&Game, 0, 0, 1);
        }
        return;
    }

    if (WaitForMessage(218)) {
        SetActorAiRoutine(&Actors[1], (AiRoutine)0x801F7F04);
        Actors[1].flags &= ~ACTOR_FLAG_INVISIBLE;
    }
}

Trigger triggers[3] = {
    {
        .enabledCallback = NULL,
        .type = TRIGGER_ON_ACTIVATE,
        .triggerCallback = cubeTrigger,
    },
    {
        .enabledCallback = NULL,
        .type = TRIGGER_ON_ACTIVATE,
        .triggerCallback = cylinderTrigger,
    },
    {
        .enabledCallback = NULL,
        .type = TRIGGER_ON_ACTIVATE,
        .triggerCallback = sphereTrigger,
    },
};

void room(GameState* game) {
    SetupRoom(&layout);
    game->currentCameraId = -1;
    game->actorLayout = &actors;
    game->backgrounds = &background;
    game->triggers = triggers;
    SetupActors(game->actorLayout);

    LoadAiModule(115);
    // mech is initially disabled
    SetActorAiRoutine(&Actors[1], NULL);
    Actors[1].flags |= ACTOR_FLAG_INVISIBLE;

    game->flagsAE8 &= ~ROOM_STATE_ROOM_INITIALIZING;
    do {
        Yield();
        // not sure exactly what flag 0x80 entails
    } while ((game->flagsAE8 & (ROOM_STATE_ROOM_LOADING | 0x80)) == 0);
}