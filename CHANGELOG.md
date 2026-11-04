# Changelog

## [1.0.0](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.5.0...league-auto-accept-v1.0.0) (2026-11-04)


### ⚠ BREAKING CHANGES

* replace Python application with native Go implementation

### Features

* add native updates and integration checks ([5d5da90](https://github.com/levyvix/league-auto-accept/commit/5d5da90c8dfdb8a4b7915b6f33a86e966fc36f55))
* add separate auto-pick and auto-ban toggles ([da6150c](https://github.com/levyvix/league-auto-accept/commit/da6150c2a8e04b54ab09b306b65edd59e74de21b))
* bootstrap native Go client and compatible settings ([51ec91e](https://github.com/levyvix/league-auto-accept/commit/51ec91e728771280876c8b8ddd6d35b8f22a5fb5))
* implement native automation and Bubble Tea interface ([c0d84bc](https://github.com/levyvix/league-auto-accept/commit/c0d84bc5262812da65dc547cba86b731745cc96e))
* replace Python application with native Go implementation ([4b5730f](https://github.com/levyvix/league-auto-accept/commit/4b5730f0288e7eee2a9937b0091ee30c74052d9e))


### Bug Fixes

* accept incoming swaps through pick order API ([7b1c74d](https://github.com/levyvix/league-auto-accept/commit/7b1c74d460454f139cab4542288789f1d3ab7a75))
* address ready check and update review findings ([0bf6323](https://github.com/levyvix/league-auto-accept/commit/0bf6323da505b518c947dde8e1823d32d80d4283))
* deduplicate champion inventory for pick and ban ([fd652e9](https://github.com/levyvix/league-auto-accept/commit/fd652e980dbe3a0a96ac0d1a3bf30b0079072cf2))
* handle unavailable champions and document native build ([3dc7ed0](https://github.com/levyvix/league-auto-accept/commit/3dc7ed0e2d4fac29220d7173b1116e4cae45b021))
* persist automatic requeue cancellation ([5a20d8b](https://github.com/levyvix/league-auto-accept/commit/5a20d8b876f6e4d2d8fc57261800c2f70d064878))

## [0.5.0](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.4.0...league-auto-accept-v0.5.0) (2026-07-25)


### Features

* select champions based on queued positions ([635ae75](https://github.com/levyvix/league-auto-accept/commit/635ae75d0624a1327b9627ecd82c8674e2ac8d9d))

## [0.4.0](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.3.0...league-auto-accept-v0.4.0) (2026-04-18)


### Features

* add wait for lobby script and enhance auto-requeue functionality ([f634513](https://github.com/levyvix/league-auto-accept/commit/f6345135b67c10b43a2b952728920e3f8fba4019))

## [0.3.0](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.2.0...league-auto-accept-v0.3.0) (2026-04-15)


### Features

* add auto-update on startup ([c0cea70](https://github.com/levyvix/league-auto-accept/commit/c0cea70f02042354ada098b16992aed2d06035d7))

## [0.2.0](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.1.1...league-auto-accept-v0.2.0) (2026-04-15)


### Features

* champion setup wizard for easier champion selection ([7e8e320](https://github.com/levyvix/league-auto-accept/commit/7e8e3209c7f6fc3f590dfdb8ea28695733344de2))

## [0.1.1](https://github.com/levyvix/league-auto-accept/compare/league-auto-accept-v0.1.0...league-auto-accept-v0.1.1) (2026-04-15)


### Bug Fixes

* include dev dependencies in CI type check ([4220b04](https://github.com/levyvix/league-auto-accept/commit/4220b04740872e65243c08efb79a7829ce47b0d1))
* suppress pyright errors for Windows-only msvcrt functions ([ba8cb8a](https://github.com/levyvix/league-auto-accept/commit/ba8cb8ad6ef85351230783dd8358f6b3e96e1c71))
* use dependency-groups instead of optional-dependencies for uv ([87dbac2](https://github.com/levyvix/league-auto-accept/commit/87dbac27e646315551803a177f2ed104f5093681))


### Documentation

* simplify README to match report-my-team style ([346b556](https://github.com/levyvix/league-auto-accept/commit/346b556e2a13c6a00cff27fb362e9824d01af14c))
