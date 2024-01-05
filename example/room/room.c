#include <galerians.h>

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
            .xSize = 7246,
            .zSize = 7246,
            .unknown10 = 0xf,
        },
        {
            .xPos = 0,
            .zPos = 0,
            .xSize = 869,
            .zSize = 869,
            .unknown10 = 0xf,
        },
    },
    .circleColliders = {
        {
            .x = 434,
            .z = 6811,
            .radius = 434,
        },
        {
            .x = 6811,
            .z = 434,
            .radius = 434,
        },
    },
    .numCameras = 1,
    .cameras = {
        {
            .orientation = 0,
            .verticalFov = 600,
            .scale = 4096,
            .x = 7246,
            .y = 4554,
            .z = 7246,
            .targetX = 5284,
            .targetY = 0,
            .targetZ = 5202,
        },
    },
    .cuts = {
        {
            .marker = 0,
            .index = 0,
            .x1 = 0,
            .z1 = 0,
            .x2 = 7246,
            .z2 = 0,
            .x3 = 0,
            .z3 = 7246,
            .x4 = 7246,
            .z4 = 7246,
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
            .xSize = 869,
            .zSize = 869,
        },
        {
            .id = 1,
            .xPos = 0,
            .zPos = 6377,
            .xSize = 869,
            .zSize = 869,
        },
        {
            .id = 2,
            .xPos = 6377,
            .zPos = 0,
            .xSize = 869,
            .zSize = 869,
        },
    },
};

ActorLayout actors = {
    .name = {'S', 'D', 'K', 'E', 'X', 0},
    .actors = {
        {
            .id = 0,
            .type = ACTOR_RION,
            .x = 3623,
            .y = 0,
            .z = 3623,
        },
        { .type = ACTOR_NONE },
        { .type = ACTOR_NONE },
        { .type = ACTOR_NONE },
    },
};

Background background = {
    .index = /* TODO: fill in with background index */,
    .numMasks = 0,
    .masks = NULL,
};

void cubeTrigger(GameState *game) {
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
}