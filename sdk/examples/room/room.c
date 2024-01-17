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
            .x = 4098,
            .y = 2968,
            .z = 4129,
            .targetX = 2684,
            .targetY = 21,
            .targetZ = 2735,
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
            .xSize = 869,
            .zSize = 869,
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
            .id = 0,
            .type = ACTOR_RION,
            .x = 1811,
            .y = 0,
            .z = 1811,
        },
        { .type = ACTOR_NONE },
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

static size_t fileItemIndex = 0;
static int32_t fileItems[] = {
    ITEM_MEDICAL_STAFF_NOTES,
    ITEM_G_PROJECT_REPORT,
    ITEM_PHOTO_OF_PARENTS,
    ITEM_RIONS_TEST_DATA,
    ITEM_DR_LEMS_NOTES,
    ITEM_NEW_REPLICATIVE_COMPUTER_THEORY,
    ITEM_DR_PASCALLES_DIARY,
    ITEM_LETTER_FROM_ELSA,
    ITEM_NEWSPAPER,
    ITEM_LETTER_FROM_LILIA
};

void cubeTrigger(GameState *game) {
    if (fileItemIndex >= 10) {
        ShowMessage(172); // It's empty.$w
    } else {
        PickupAnimation pickupAnimation = {
            .soundSet = NULL,
            .soundId = 0,
            .voiceIndex = 0,
            .x = 450,
            .z = 450,
            .angle = 1024,
            .cameraId = 0
        };
        PickUpKeyItem(game, fileItems[fileItemIndex], 28 + fileItemIndex, ITEM_PICKUP_RESTORE_CAMERA, &pickupAnimation); // NoMessage
        ++fileItemIndex;
    }
}

void cylinderTrigger(GameState *game) {
}

void sphereTrigger(GameState *game) {
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

void room(GameState *game) {
    SetupRoom(&layout);
    game->currentCameraId = -1;
    game->actorLayout = &actors;
    game->backgrounds = &background;
    game->triggers = triggers;
    SetupActors(game->actorLayout);

    game->flagsAE8 &= ~ROOM_STATE_ROOM_INITIALIZING;
    do {
        Yield();
        // not sure exactly what flag 0x80 entails
    } while ((game->flagsAE8 & (ROOM_STATE_ROOM_LOADING | 0x80)) == 0);
}