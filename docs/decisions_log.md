# Decisions Log

| Date | Decision | Reason |
|---|---|---|
| 2026-05-02 | Use the 114-record processed dataset for the current workflow | Avery confirmed that the 114-record layers are the current working dataset, even though the proposal referenced 95 sites |
| 2026-05-02 | Use `park_num` as the linking field between reach and haptic layers | `park_num`, `PARK_NAME`, and `MUNI` matched across all 114 reach and haptic records |
| 2026-05-02 | Use separate scripts for reach and haptic workflows | This keeps the workflow modular and easier to build on in future weeks |
| 2026-05-02 | Create `week1.py` to combine Week 1 outputs | Week-specific output can call reusable functions from `reach.py` and `haptic.py` |