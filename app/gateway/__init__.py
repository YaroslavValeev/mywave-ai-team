# app/gateway — единая точка секретов и dangerous actions
# Gateway Layer: держит секреты, выдаёт агентам только capabilities,
# запускает опасные операции изолированно.
#
# Основание: OpenClaw/Molted — минимум секретов у агентов, максимум у gateway.
