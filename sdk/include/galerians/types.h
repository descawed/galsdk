#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

#define assert_size(T, S) _Static_assert(sizeof(T) == S, "sizeof(" #T ") not correct")

// we need some types from the PSX SDK. if PSYQ isn't available, we'll define them ourselves.
#ifdef GALERIANS_USE_PSYQ
#include <LIBGTE.H>

// we want to make sure all these types use the exact layout reverse-engineered from the game. #pragma pack is a
// Microsoft feature, but both GCC and clang support it, and I don't want to have to type __attribute__((__packed__))
// over and over again.
#pragma pack(push, 1)
#else
#pragma pack(push, 1)

typedef struct _MATRIX {
    int16_t m[3][3]; // 00
    int16_t pad;     // 12
    int32_t t[3];    // 14
} MATRIX;
assert_size(MATRIX, 0x20);

typedef struct _VECTOR {
    int32_t vx;  // 00
    int32_t vy;  // 04
    int32_t vz;  // 08
    int32_t pad; // 0C
} VECTOR;
assert_size(VECTOR, 0x10);

typedef struct _SVECTOR {
    int16_t vx;  // 00
    int16_t vy;  // 02
    int16_t vz;  // 04
    int16_t pad; // 06
} SVECTOR;
assert_size(SVECTOR, 8);

typedef struct _CVECTOR {
    uint8_t r;  // 00
    uint8_t g;  // 01
    uint8_t b;  // 02
    uint8_t cd; // 03
} CVECTOR;
assert_size(CVECTOR, 4);
#endif

// forward declarations
typedef struct _GameState GameState;
typedef struct _Actor Actor;

/**
 * Type of a collider object.
 */
#define COLLIDER_WALL   0
#define COLLIDER_RECT   1
#define COLLIDER_TRI    2
#define COLLIDER_CIRCLE 3

/**
 * A solid object in the room that the player can't pass through.
 */
typedef struct _Collider {
    uint32_t type;      // 00
    void* shape;        // 04
    int32_t unknown08;  // 08
} Collider;
assert_size(Collider, 0x0C);

/**
 * A rectangular collision shape.
 */
typedef struct _RectangleCollider {
    int32_t xPos;       // 00
    int32_t zPos;       // 04
    int32_t xSize;      // 08
    int32_t zSize;      // 0C
    int32_t unknown10;  // 10
} RectangleCollider;
assert_size(RectangleCollider, 0x14);

/**
 * A triangular collision shape.
 */
typedef struct _TriangleCollider {
    int32_t x1;     // 00
    int32_t z1;     // 04
    int32_t x2;     // 08
    int32_t z2;     // 0C
    int32_t x3;     // 10
    int32_t z3;     // 14
} TriangleCollider;
assert_size(TriangleCollider, 0x18);

/**
 * A circular collision shape.
 */
typedef struct _CircleCollider {
    int32_t x;      // 00
    int32_t z;      // 04
    int32_t radius; // 08
} CircleCollider;
assert_size(CircleCollider, 0x0C);

/**
 * A camera view in a room.
 */
typedef struct _Camera {
    int16_t orientation;    // 00
    int16_t verticalFov;    // 02
    int16_t scale;          // 04
    int16_t x;              // 06
    int16_t y;              // 08
    int16_t z;              // 0A
    int16_t targetX;        // 0C
    int16_t targetY;        // 0E
    int16_t targetZ;        // 10
    int16_t unknown12;      // 12
} Camera;
assert_size(Camera, 0x14);

/**
 * A region that triggers a cut to a specific camera angle when the player enters it.
 */
typedef struct _CameraCut {
    int16_t marker;     // 00
    int16_t index;      // 02
    int32_t x1;         // 04
    int32_t z1;         // 08
    int32_t x2;         // 0C
    int32_t z2;         // 10
    int32_t x3;         // 14
    int32_t z3;         // 18
    int32_t x4;         // 1C
    int32_t z4;         // 20
} CameraCut;
assert_size(CameraCut, 0x24);

/**
 * An area that the player can interact with.
 */
typedef struct _Interactable {
    int16_t id;     // 00
    int16_t xPos;   // 02
    int16_t zPos;   // 04
    int16_t xSize;  // 06
    int16_t zSize;  // 08
} Interactable;
assert_size(Interactable, 0x0A);

/**
 * Types of events that can cause a trigger to fire.
 */
#define TRIGGER_ALWAYS              0
#define TRIGGER_NOT_ATTACKING       1
#define TRIGGER_ON_ACTIVATE         2
// the game has three types of scan triggers, which seems to be related to a cut feature where you would have been able
// to combine scanning with an item. when the game checks if a trigger should be executed, it passes two pieces of
// information - the type of action happening (walking into the trigger, using, or scanning) and an optional item ID.
// when you scan, the item ID is hard-coded to 6 (Liquid Explosive). TRIGGER_ON_SCAN_HARDCODED is also hard-coded to
// require an item ID of 6, so in practice, it just triggers on any scan. TRIGGER_ON_SCAN doesn't check the item ID,
// so it also triggers on any scan. TRIGGER_ON_SCAN_WITH_ITEM lets you specify a specific item to check for. since the
// input item is always 6, it will just never trigger if the item to check for is anything other than 6. in practice,
// the game always uses TRIGGER_ON_SCAN_HARDCODED.
#define TRIGGER_ON_SCAN_HARDCODED   3
#define TRIGGER_ON_SCAN             4
#define TRIGGER_ON_SCAN_WITH_ITEM   5
#define TRIGGER_ON_USE_ITEM         6

/**
 * Key items and files.
 */
#define ITEM_MEMORY_CHIP_15F                     0
#define ITEM_SECURITY_CARD                       1
#define ITEM_BEEJECT                             2
#define ITEM_FREEZER_ROOM_KEY                    3
#define ITEM_PPEC_STORAGE_KEY                    4
#define ITEM_FUSE                                5
#define ITEM_LIQUID_EXPLOSIVE                    6
#define ITEM_MEMORY_CHIP_14F                     7
#define ITEM_SECURITY_CARD_REFORMATTED           8
#define ITEM_SPECIAL_PPEC_OFFICE_KEY             9
#define ITEM_MEMORY_CHIP_13F                    10
#define ITEM_TEST_LAB_KEY                       11
#define ITEM_CONTROL_ROOM_KEY                   12
#define ITEM_RESEARCH_LAB_KEY                   13
#define ITEM_TWO_HEADED_SNAKE                   14
#define ITEM_TWO_HEADED_MONKEY                  15
#define ITEM_TWO_HEADED_WOLF                    16
#define ITEM_TWO_HEADED_EAGLE                   17
#define ITEM_YOUR_HOUSE_MEMORY_CHIP             18
#define ITEM_BACKDOOR_KEY                       19
#define ITEM_DOOR_KNOB                          20
#define ITEM_9_BALL                             21
#define ITEM_MOTHERS_RING                       22
#define ITEM_FATHERS_RING                       23
#define ITEM_LILIAS_DOLL                        24
#define ITEM_METAMORPHOSIS                      25
#define ITEM_BEDROOM_KEY                        26
#define ITEM_SECOND_FLOOR_KEY                   27
#define ITEM_MEDICAL_STAFF_NOTES                28
#define ITEM_G_PROJECT_REPORT                   29
#define ITEM_PHOTO_OF_PARENTS                   30
#define ITEM_RIONS_TEST_DATA                    31
#define ITEM_DR_LEMS_NOTES                      32
#define ITEM_NEW_REPLICATIVE_COMPUTER_THEORY    33
#define ITEM_DR_PASCALLES_DIARY                 34
#define ITEM_LETTER_FROM_ELSA                   35
#define ITEM_NEWSPAPER                          36
#define ITEM_3_BALL                             37
#define ITEM_SHED_KEY                           38
#define ITEM_LETTER_FROM_LILIA                  39
#define ITEM_DFELON                             40

/**
 * An action to be triggered when interacting with an interactable region.
 */
typedef struct _Trigger {
    int32_t (*enabledCallback)(GameState*); // 00
    uint8_t type;                           // 04
    uint8_t flags;                          // 05
    uint16_t itemId;                        // 06
    void (*triggerCallback)(GameState*);    // 08
    uint32_t unknown0C;                     // 0C
} Trigger;
assert_size(Trigger, 0x10);

/**
 * Layout of collision objects and cameras in a room.
 */
typedef struct _RoomLayout {
    uint32_t numColliders;                  // 0000
    Collider colliders[100];                // 0004
    RectangleCollider rectColliders[100];   // 04B4
    TriangleCollider triColliders[100];     // 0C84
    CircleCollider circleColliders[100];    // 15E4
    uint32_t numCameras;                    // 1A94
    Camera cameras[10];                     // 1A98
    CameraCut cuts[10];                     // 1B60
    uint8_t unknown1CC8[0xca8];             // 1CC8
    uint32_t numInteractables;              // 2970
    Interactable interactables[100];        // 2974
} RoomLayout;
assert_size(RoomLayout, 0x2D5C);

/**
 * An image overlaid on the background at a certain depth.
 */
typedef struct _BackgroundMask {
    uint32_t index;     // 00
    uint32_t unknown04; // 04
    int16_t x;          // 08
    int16_t y;          // 0A
    int16_t z;          // 0C
    int16_t unknown0E;  // 0E
} BackgroundMask;
assert_size(BackgroundMask, 0x10);

/**
 * The background image for a camera angle with any associated masks.
 */
typedef struct _Background {
    int16_t index;          // 00
    uint16_t numMasks;      // 02
    BackgroundMask* masks;  // 04
} Background;
assert_size(Background, 8);

/**
 * One segment of a 3D model.
 *
 * A model can contain up to 19 segments. Actor model segments are connected in a hard-coded hierarchy that varies by
 * actor type. Segments of other model types are not explicitly connected in any way.
 */
typedef struct _ModelSegment {
    uint16_t segmentIndex;      // 00
    uint16_t unknown02;         // 02
    int32_t* (*prims)[4];       // 04
    uint8_t unknown08[128];     // 08
    MATRIX rotMatrix;           // 88
    VECTOR fullTfmModelOffsets; // A8
    SVECTOR transVector;        // B8
    SVECTOR rotEndVector;       // C0
    int32_t offsetX;            // C8
    int32_t offsetY;            // CC
    int32_t offsetZ;            // D0
    SVECTOR rotStartVector;     // D4
    uint8_t unknownDC[16];      // DC
    SVECTOR unknownEC;          // EC
} ModelSegment;
assert_size(ModelSegment, 0xF4);

/**
 * Essentially an SVECTOR without the padding at the end.
 */
typedef struct _AnimationVector {
    int16_t x;  // 00
    int16_t y;  // 02
    int16_t z;  // 04
} AnimationVector;
assert_size(AnimationVector, 6);

/**
 * Flags controlling animation behavior for a single animation frame.
 */
#define ANIM_FLIP_HIT_SEGMENTS      0x00000001
#define ANIM_SEGMENT_1_HIT          0x00000002
#define ANIM_SEGMENT_2_HIT          0x00000004
#define ANIM_SEGMENT_3_HIT          0x00000008
#define ANIM_SEGMENT_4_HIT          0x00000010
#define ANIM_SEGMENT_5_HIT          0x00000020
#define ANIM_SEGMENT_6_HIT          0x00000040
#define ANIM_SEGMENT_7_HIT          0x00000080
#define ANIM_SEGMENT_8_HIT          0x00000100
#define ANIM_SEGMENT_9_HIT          0x00000200
#define ANIM_SEGMENT_10_HIT         0x00000400
#define ANIM_SEGMENT_11_HIT         0x00000800
#define ANIM_SEGMENT_12_HIT         0x00001000
#define ANIM_SEGMENT_13_HIT         0x00002000
#define ANIM_SEGMENT_14_HIT         0x00004000
#define ANIM_SEGMENT_15_HIT         0x00008000
#define ANIM_UNKNOWN_16             0x00010000
#define ANIM_UNKNOWN_17             0x00020000
#define ANIM_UNKNOWN_18             0x00040000
#define ANIM_FACE_TARGET            0x00080000
#define ANIM_UNKNOWN_20             0x00100000
#define ANIM_UNKNOWN_21             0x00200000
#define ANIM_UNKNOWN_22             0x00400000
#define ANIM_UNKNOWN_23             0x00800000
#define ANIM_UNKNOWN_24             0x01000000
#define ANIM_UNKNOWN_25             0x02000000
#define ANIM_UNKNOWN_26             0x04000000
#define ANIM_UNKNOWN_27             0x08000000
#define ANIM_UNKNOWN_28             0x10000000
#define ANIM_FORWARD                0x20000000
#define ANIM_TOGGLE_DIRECTION       0x40000000
#define ANIM_END                    0x80000000

/**
 * A single frame of an animation.
 */
typedef struct _AnimationFrame {
    AnimationVector rotationVectors[16];    // 00
    uint32_t flags;                         // 60
} AnimationFrame;
assert_size(AnimationFrame, 0x64);

/**
 * The different types of actors (characters/enemies/NPCs) in the game.
 */
#define ACTOR_NONE                      -1
#define ACTOR_RION                       0
#define ACTOR_LILIA                      1
#define ACTOR_LEM                        2
#define ACTOR_BIRDMAN                    3
#define ACTOR_RAINHEART                  4
#define ACTOR_RITA                       5
#define ACTOR_CAIN                       6
#define ACTOR_CROVIC                     7
#define ACTOR_JOULE                      8
#define ACTOR_LEM_ROBOT                  9
#define ACTOR_GUARD_HOSPITAL_SKINNY     10
#define ACTOR_GUARD_HOSPITAL_BURLY      11
#define ACTOR_GUARD_HOSPITAL_GLASSES    12
#define ACTOR_MECH                      13
#define ACTOR_HAZARD_MECH               14
#define ACTOR_SNIPER                    15
#define ACTOR_DOCTOR_BROWN_HAIR         16
#define ACTOR_DOCTOR_BLONDE             17
#define ACTOR_DOCTOR_BALD               18
#define ACTOR_RABBIT_KNIFE              19
#define ACTOR_RABBIT_TRENCH_COAT        20
#define ACTOR_ARABESQUE_BIPED           21
#define ACTOR_KNOCK_GUY                 22
#define ACTOR_DANCER                    23
#define ACTOR_HOTEL_RECEPTIONIST        24
#define ACTOR_ARMS_DEALER               25
#define ACTOR_TERRORIST                 26
#define ACTOR_PRIEST                    27
#define ACTOR_RAINHEART_HAT             28
#define ACTOR_MECH_UNUSED               29
#define ACTOR_RABBIT_UNARMED            30
#define ACTOR_ARABESQUE_QUADRUPED       31
#define ACTOR_KNOCK_GUY_2               32
#define ACTOR_RAINHEART_SUMMON          33
#define ACTOR_CROVIC_PROP               34
#define ACTOR_DOROTHY_EYE               35
#define ACTOR_RION_PHONE                36
#define ACTOR_RION_ALT_1                37
#define ACTOR_RION_ALT_2                38

/**
 * The initial health value for an actor in a new game.
 *
 * This is per actor instance, not actor type, so two actors of the same type can have different amounts of health. In
 * the Japanese version, these values are loaded from module 129. In other versions, they're hard-coded in the EXE.
 */
typedef struct _ActorInitialHealth {
    int16_t health;     // 00
    int16_t unknown02;  // 02
} ActorInitialHealth;
assert_size(ActorInitialHealth, 4);

/**
 * A placed instance of an actor in a room.
 */
typedef struct _ActorInstance {
    uint16_t id;        // 00
    int16_t type;       // 02
    int16_t x;          // 04
    int16_t y;          // 06
    int16_t z;          // 08
    uint16_t unknown0A; // 0A
    uint16_t angle;     // 0C
    uint16_t unknown0E; // 0E
} ActorInstance;
assert_size(ActorInstance, 0x10);

/**
 * The layout of actors in a room.
 */
typedef struct _ActorLayout {
    char name[6];               // 00
    uint8_t unknown06[30];      // 06
    ActorInstance actors[4];    // 24
} ActorLayout;
assert_size(ActorLayout, 0x64);

/**
 * Game stages.
 */
#define STAGE_A 0
#define STAGE_B 1
#define STAGE_C 2
#define STAGE_D 3

/**
 * Game maps.
 *
 * The rooms of each stage are organized into maps, roughly corresponding to the different floors of the building.
 */
#define MAP_HOSPITAL_15F    0
#define MAP_HOSPITAL_14F    1
#define MAP_HOSPITAL_13F    2
#define MAP_YOUR_HOUSE_1F   3
#define MAP_YOUR_HOUSE_2F   4
#define MAP_HOTEL_1F        5
#define MAP_HOTEL_2F        6
#define MAP_HOTEL_3F        7
#define MAP_MUSHROOM_TOWER  8

/**
 * A room in a given map.
 */
typedef struct _MapRoom {
    uint32_t moduleIndex;           // 00
    void (*entryPoint)(GameState*); // 04
} MapRoom;

/**
 * Player psychic power abilities.
 */
#define ABILITY_NALCON  0
#define ABILITY_RED     1
#define ABILITY_DFELON  2

/**
 * Medicine items.
 */
#define MEDICINE_NONE       -1
#define MEDICINE_NALCON      1
#define MEDICINE_RED         2
#define MEDICINE_DFELON      3
#define MEDICINE_RECOVERY    4
#define MEDICINE_DELMETOR    5
#define MEDICINE_APPOLLINAR  6
#define MEDICINE_SKIP        7

/**
 * Various game state flags.
 */
// flagsAE8
#define STATE_SHOW_MESSAGE  4
// flags03C
#define STATE_INTERACTING           2
#define STATE_DISPLAYING_MESSAGE    4

#define ROOM_STATE_MAP_CHANGING         0x02
#define ROOM_STATE_ROOM_CHANGING        0x04
#define ROOM_STATE_STAGE_CHANGING       0x08
#define ROOM_STATE_QUIT_GAME            0x10
#define ROOM_STATE_ROOM_LOADING         0x20
#define ROOM_STATE_ROOM_INITIALIZING    0x40

/**
 * Current state of the game.
 */
struct _GameState {
    uint32_t stageId;                           // 000
    uint16_t mapId;                             // 004
    uint16_t lastMapId;                         // 006
    uint32_t unknown008;                        // 008
    uint16_t roomId;                            // 00C
    int16_t lastRoom;                           // 00E
    uint8_t numCameras;                         // 010
    uint8_t currentCameraId;                    // 011
    int8_t newCameraIndex;                      // 012
    uint8_t pad013;                             // 013
    Camera* cameras;                            // 014
    Background* backgrounds;                    // 018
    CameraCut* cuts;                            // 01C
    uint32_t unknown020;                        // 020
    int16_t numTriggers;                        // 024
    int16_t unknown026;                         // 026
    int16_t activeTriggerId;                    // 028
    uint16_t unknown02A;                        // 02A
    ActorLayout* actorLayout;                   // 02C
    Trigger* triggers;                          // 030
    Interactable* interactables;                // 034
    MapRoom* map;                               // 038
    uint32_t flags03C;                          // 03C
    uint32_t flags040;                          // 040
    int32_t messageId;                          // 044
    // the Japanese version of this struct is smaller here than other versions. from this point on, we'll name unknown
    // fields based on the offsets in Western versions.
    #ifdef GALERIANS_REGION_JAPAN
    uint8_t unknown048[1556];                   // 048
    #else
    uint8_t unknown048[1564];                   // 048
    #endif
    uint16_t ap;                                // 664 / 65C
    uint16_t apFraction;                        // 666 / 65E
    uint16_t isShorting;                        // 668 / 660
    uint16_t playerHealth;                      // 66A / 662
    uint32_t equippedAbility;                   // 66C / 664
    int32_t abilityLevels[7];                   // 670 / 668
    uint16_t skipLevel;                         // 68C / 684
    uint8_t unknown68E[10];                     // 68E / 686
    uint64_t stateFlags1[4];                    // 698 / 690
    uint64_t stateFlags2[4];                    // 6B8 / 6B0
    uint64_t stateFlags3[4];                    // 6D8 / 6D0
    uint8_t unknown6F8[8];                      // 6F8 / 6F0
    uint32_t keyItemOffsets[41];                // 700 / 6F8
    int16_t keyItems[41];                       // 7A4 / 79C
    uint16_t numKeyItems;                       // 7F6 / 7EE
    int16_t medicineItems[20];                  // 7F8 / 7F0
    uint64_t mapVisitedRoomFlags[9];            // 820 / 818
    ActorInitialHealth actorsInitialHealth[138];// 868 / 860
    uint8_t unknownA90[12];                     // A90 / A88
    uint16_t newGamePlus;                       // A9C / A94
    int16_t unknownA9E[33];                     // A9E / A96
    uint32_t unknownAE0;                        // AE0 / AD8
    uint32_t unknownAE4;                        // AE4 / ADC
    uint32_t flagsAE8;                          // AE8 / AE0
};
#ifdef GALERIANS_REGION_JAPAN
assert_size(GameState, 0xAE4);
#else
assert_size(GameState, 0xAEC);
#endif

/**
 * The position of one actor relative to another.
 */
typedef struct _ActorRelativePosition {
    int16_t type;
    int16_t angle;
    int32_t distanceSquared;
} ActorRelativePosition;
assert_size(ActorRelativePosition, 8);

/**
 * Description of a melee attack.
 */
typedef struct _MeleeAttack {
    uint16_t unknown00; // 00
    uint16_t hitAngle;  // 02
    uint16_t unknown04; // 04
    uint16_t damage;    // 06
    uint8_t type;       // 08
    uint8_t pad09;      // 09
    uint16_t unknown0A; // 0A
} MeleeAttack;
assert_size(MeleeAttack, 0x0C);

/**
 * Description of a ranged attack.
 */
typedef struct _RangedAttack {
    uint8_t type;   // 00
    uint8_t pad01;  // 01
    int16_t value;  // 02
} RangedAttack;
assert_size(RangedAttack, 4);

/**
 * Actor state/behavior flags.
 */
#define ACTOR_FLAG_REVERSE_ANIMATION    0x0001
#define ACTOR_FLAG_SKIP_TRANSLATE       0x0004
#define ACTOR_FLAG_EQUIP_NEXT_ATTACK    0x0010
#define ACTOR_FLAG_CAN_ATTACK           0x0020
#define ACTOR_FLAG_CHARGING             0x0400
#define ACTOR_FLAG_INVISIBLE            0x8000

/**
 * Actor AI states.
 */
#define AI_IDLE             0x00
#define AI_ALERT            0x01
#define AI_START_ATTACK     0x02
#define AI_ATTACK           0x03
#define AI_FINISH_ATTACK    0x04
#define AI_CHARGE_ATTACK    0x06
#define AI_STAGGER          0x0c
#define AI_DIE              0x0e
#define AI_FALL             0x11
#define AI_KNOCKED_DOWN     0x14
#define AI_GET_UP           0x16
#define AI_DEAD             0x18
#define AI_GRABBED          0x22
#define AI_THROWN           0x23

/**
 * Actor AI routine.
 */
typedef int32_t (*AiRoutine)(GameState*, Actor*);

/**
 * An instance of an actor in the current room.
 */
struct _Actor {
    uint16_t instanceIndex;                     // 0000
    uint16_t instanceId;                        // 0002
    int16_t actorType;                          // 0004
    uint8_t unknown0008[14];                    // 0008
    CVECTOR lightingColor;                      // 0014
    CVECTOR shadowColor;                        // 0018
    uint8_t unknown001C[72];                    // 001C
    uint16_t tPageId;                           // 0064
    uint16_t unknown0066;                       // 0066
    uint32_t clutId;                            // 0068
    uint8_t unknown006C[6];                     // 006C
    int16_t animationId;                        // 0072
    uint16_t animFrameSize;                     // 0074
    int16_t animDataOffset;                     // 0076
    AnimationFrame (*animation)[100];           // 0078
    AnimationFrame* currentAnimFrame;           // 007C
    int16_t unknownIndex0080;                   // 0080
    int16_t unknown0082;                        // 0082
    uint16_t* unknown0084;                      // 0084
    ModelSegment segments[20];                  // 0088
    uint16_t numSegments;                       // 1398
    uint8_t unknown139A[16];                    // 139A
    uint16_t showHeldObject;                    // 13AA
    ModelSegment unknownSegment;                // 13AC
    uint8_t unknown14A0[684];                   // 14A0
    MeleeAttack* equippedAttack;                // 174C
    MeleeAttack* hitByAttack;                   // 1750
    MeleeAttack* incomingAttack;                // 1754
    RangedAttack rangedAttack;                  // 1758
    int16_t timer1;                             // 175C
    int16_t timer2;                             // 175E
    int16_t timer3;                             // 1760
    int16_t timer4;                             // 1762
    uint8_t unknown1764[8];                     // 1764
    uint16_t unknown176C;                       // 176C
    uint16_t currentHitType;                    // 176E
    uint16_t incomingHitType;                   // 1770
    uint16_t attackerHitAngle;                  // 1772
    uint16_t attackerActorIndex;                // 1774
    uint16_t attackerAnimationIndex;            // 1776
    uint8_t unknown1778[24];                    // 1778
    ActorRelativePosition actorPositions[4];    // 1790
    int16_t actorIndexesByDistance[3];          // 17B0
    uint8_t unknown17B6[4];                     // 17B6
    int16_t animProgress;                       // 17BA
    int32_t interactionX;                       // 17BC
    int32_t interactionY;                       // 17C0
    int32_t interactionZ;                       // 17C4
    int32_t x;                                  // 17C8
    int32_t y;                                  // 17CC
    int32_t z;                                  // 17D0
    int32_t unkX1;                              // 17D4
    int32_t unkY1;                              // 17D8
    int32_t unkZ1;                              // 17DC
    int32_t unkX2;                              // 17E0
    int32_t unkY2;                              // 17E4
    int32_t unkZ2;                              // 17E8
    int32_t unknown17EC;                        // 17EC
    int32_t unknown17F0;                        // 17F0
    int32_t unknown17F4;                        // 17F4
    uint8_t unknown17F8[28];                    // 17F8
    int16_t angle;                              // 1814
    int16_t angleOffset;                        // 1816
    int16_t unknown1818;                        // 1818
    uint16_t unknown181A;                       // 181A
    uint8_t unknown181C[4];                     // 181C
    int16_t unknown1820;                        // 1820
    int16_t originalHealth;                     // 1822
    int16_t health;                             // 1824
    int16_t minimumHealth;                      // 1826
    uint16_t unknownCharge1828;                 // 1828
    int16_t attackChargeLevel;                  // 182A
    uint16_t stdAnimationOffset;                // 182C
    int16_t currentChargeLevel;                 // 182E
    int16_t unknown1830;                        // 1830
    uint16_t unknown1832;                       // 1832
    void* soundSet;                             // 1834
    uint8_t unknown1838[32];                    // 1838
    uint32_t flags;                             // 1858
    uint16_t aiState;                           // 185C
    uint16_t unknown185E;                       // 185E
    uint16_t unknown1860;                       // 1860
    uint8_t unknown1862[4];                     // 1862
    int16_t unknown1866;                        // 1866
    uint32_t flags1868;                         // 1868
    uint32_t unknown186C;                       // 186C
    uint32_t flags1870;                         // 1870
    int32_t minAttackDistanceSquared;           // 1874
    int32_t unknown1878;                        // 1878
    AiRoutine aiRoutine;                        // 187C
    uint8_t unknown1880[64];                    // 1880
};
assert_size(Actor, 0x18C0);

/**
 * Description of a database (CDB) file.
 */
typedef struct _Database {
  uint32_t isExtended;              // 00
  char path[20];                    // 04
  uint8_t gap18[60];                // 18
  void* directory;                  // 54
  int32_t unknown58;                // 58
  uint32_t unknown5C;               // 5C
  uint32_t unknown60;               // 60
  uint32_t fileStartSector;         // 64
  uint32_t entryStartSector;        // 68
  uint32_t entryNumSectors;         // 6C
  uint16_t entryToLoad;             // 70
  uint16_t lastSectorSize;          // 72
} Database;
assert_size(Database, 0x74);

/**
 * Array of colliders used in the current room.
 */
typedef struct _ColliderArray {
    uint32_t numColliders;  // 00
    Collider* colliders;    // 04
} ColliderArray;
assert_size(ColliderArray, 8);

/**
 * Flags related to picking up an item.
 */
#define ITEM_PICKUP_RESTORE_CAMERA  0x01
// default animation is crouch
#define ITEM_PICKUP_ANIM_STAND      0x02
#define ITEM_PICKUP_ANIM_STEP       0x04
#define ITEM_PICKUP_NO_MODEL        0x80

/**
 * Position and sound information for playing an item pick-up animation.
 */
typedef struct _PickupAnimation {
    void* soundSet;     // 00
    int16_t soundId;    // 04
    int16_t voiceIndex; // 06
    int16_t x;          // 08
    int16_t z;          // 0A
    uint16_t angle;     // 0C
    int16_t cameraId;   // 0E
} PickupAnimation;
assert_size(PickupAnimation, 0x10);

#pragma pack(pop)

#ifdef __cplusplus
}
#endif