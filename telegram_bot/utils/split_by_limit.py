MESSAGE_MAX_LENGTH = 4096


def split_message_by_limit(blocks: list[str]) -> list[str]:
    start_idx = 0
    current_length = 0
    messages = []
    for i, part in enumerate(blocks):
        part_length = len(part) + 1
        if current_length + part_length > MESSAGE_MAX_LENGTH:
            messages.append("\n".join(blocks[start_idx:i]))
            start_idx = i
            current_length = 0
        current_length += part_length

    if start_idx < len(blocks):
        messages.append("\n".join(blocks[start_idx:]))

    return messages
