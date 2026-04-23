# Remote Mode Isolation Strategy

This branch introduces a LAN-only remote mode without breaking the existing local-first workflow.

## Decisions

1. Keep local mode as the default.
2. Remote mode is opt-in and disabled by default.
3. No cloud/SaaS/account/auth features are added.
4. Controller and Worker responsibilities are separated.
5. Existing local API/UI/overlay behavior must remain unchanged when remote mode is off.

## Folder Lock

- `SST desktop remote SST/`: test workspace for remote mode experiments.
- `desktop remote clean/`: clean workspace for publish validation and clean-start checks.

## Safe Implementation Rules

1. Add remote config behind explicit flags only.
2. Do not change existing defaults for local startup.
3. Add separate runtime entry points for Controller and Worker.
4. Keep subtitle routing on Controller side.
5. Keep ASR+translation execution on Worker side in remote mode.
6. Add reconnect and heartbeat for LAN instability.

## Exit Criteria For Remote Work

1. Local mode still works with no remote setup.
2. Remote mode works inside one LAN with explicit enable.
3. Overlay and export stay on Controller side.
4. Worker can run AI-only pipeline from incoming WebRTC audio.
