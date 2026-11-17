# 插件 API

Thermal Ledger 的核心不包含任何厂商专用逻辑。传感器、风扇、负载都通过接口 + Python entry points 接入。

## 1. 传感器

```python
from thermal_ledger.sensors.base import SensorSnapshot

class MySensor:
    id = "my-sensor"
    name = "My sensor"

    def available(self) -> bool:
        return True

    def read(self) -> SensorSnapshot:
        return SensorSnapshot(ts=..., temp_c=..., power_w=..., hotspot_c=None)

    def close(self) -> None:
        pass
```

`SensorSnapshot` 里温度/功耗允许为 `None`，不要用 0 或假数据填充。

## 2. 风扇（只读）

```python
class MyFan:
    id = "my-vendor-fan"
    name = "Vendor EC fan"

    def available(self) -> bool:
        return True

    def read_rpm(self) -> int | None:
        return 2400  # 读不到必须返回 None

    def close(self) -> None:
        pass
```

厂商差异（Acer/Lenovo/ASUS/HP/蓝天/神舟…）全部限制在这一层；
如果读不到，返回 `None`，GUI 显示 `--`，绝不伪造。

## 3. 负载

```python
class MyLoad:
    id = "my-load"
    name = "My load"
    description = "..."

    def available(self) -> bool: ...
    def start(self) -> None: ...
    def poll(self, stop: threading.Event) -> None: ...
    def stop(self) -> None: ...
```

要求：

- `start()` 不能阻塞 UI；
- `stop()` 必须能快速结束；
- 崩溃/异常写进 `self.error`，不要拖垮主程序；
- 需要温度保护时由核心的 cutoff 负责，插件只负责产生/管理负载。

## 4. 注册 entry points

`pyproject.toml`：

```toml
[project.entry-points."thermal_ledger.sensors"]
my-sensor = "my_pkg.sensor:MySensor"

[project.entry-points."thermal_ledger.fans"]
my-vendor-fan = "my_pkg.fan:MyFan"

[project.entry-points."thermal_ledger.loads"]
my-load = "my_pkg.load:MyLoad"
```

安装插件包后，GUI 的下拉框会自动出现对应 ID。

## 5. 约定

- 只读优先：风扇/传感器插件不得修改风扇曲线、电压或功耗；
- 单位：温度 °C，功耗 W，风扇 RPM；
- 失败要显式：`available()` 返回 False 或 `None`，不要静默填 0；
- 厂商代码放在独立发行包，不要进核心仓库。
