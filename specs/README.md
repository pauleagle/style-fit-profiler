# Style Fit Profiler Specs

本資料夾存放從 root `SPEC.md` 拆出的細部規格資料。

## 分工

- `../SPEC.md` 保留目前目標版本的 root correctness index、accepted baseline behavior、acceptance criteria 與高階 testing implications。
- `backlog/` 存放 post-P0 experimental specs、change requests、Devil's Advocate drill-down registers 與 future planning material。
- Backlog files 預設不是 accepted implementation scope；除非 root `SPEC.md` 或 active workflow 明確提升該項目。

## 狀態詞

- `accepted`：active correctness source，可進入 implementation。
- `post-P0`：目前 Phase 0 baseline 之後的 planning scope。
- `experimental`：opt-in 或探索性行為，不得改變 baseline defaults。
- `blocked`：需要 drill-down resolution 或 human decision，才可進入 atomic decomposition。
- `ready-for-atomic-decomposition`：blocking DA gate 已收斂，可開始拆 atomic items；
  仍不等同於 accepted implementation scope。
- `deferred`：future work，不阻擋目前 baseline。

## Index

- [Backlog Specs](backlog/README.md)
