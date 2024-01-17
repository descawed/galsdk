#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <galerians/types.h>

extern GameState Game;
extern Actor Actors[4];
extern uint16_t FrameCount;
extern uint32_t CircleWallThreshold;

extern Database BgTimADb;
extern Database BgTimBDb;
extern Database BgTimCDb;
extern Database BgTimDDb;
extern Database DisplayDb;
extern Database ItemTimDb;
extern Database MotDb;
extern Database MenuDb;
extern Database ModelDb;
extern Database SoundDb;
extern Database ModuleDb;
#ifdef GALERIANS_REGION_JAPAN
extern Database ChkDb;
extern Database MesDb;
extern Database TitDb;
extern Database CardDb;
extern Database FontDb;
#endif

#ifdef __cplusplus
}
#endif