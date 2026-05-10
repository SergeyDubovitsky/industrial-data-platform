# Future Ideas

Этот файл хранит только идеи и возможные следующие инкременты.

Он не является execution backlog.
Текущие задачи, приоритеты и статус выполнения ведутся во внутреннем issue
tracker.

## Ideas

- Экспортёр `knxproj -> Edge Agent config`
  Кратко: преобразовывать данные парсера в versioned YAML config bundle,
  брать `point_ref` из `KNX group address`,
  нормализовывать `DPT -> value_model/value_type`, подсказывать `signal_type`
  и явно помечать точки, где нужен `manual override`.

- Архитектура голосового управления без подключения к интернету для управления устройствами
