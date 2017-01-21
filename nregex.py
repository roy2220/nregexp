_STATE_TYPE_SPLIT = 256
_STATE_TYPE_MATCH = 257
_STATE_TYPE_ANYCHAR = 258


_state_list_id = -1


class _CharStream(object):
    def __init__(self, string):
        self._string = string
        self._index = 0

    def is_at_end(self):
        return self._index == len(self._string)

    def get_char(self):
        if self.is_at_end():
            raise EOFError()

        char = ord(self._string[self._index])
        self._index += 1
        return char

    def peek_char(self):
        if self.is_at_end():
            return None
        else:
            char = ord(self._string[self._index])
            return char

    def discard_char(self):
        self._index += 1


def _is_meta_char(char):
    return char in (ord("?"), ord("+"), ord("*"), ord("|"))


def _unescape_char(char_stream):
    char = char_stream.get_char()

    if not (_is_meta_char(char) or char in (ord("\\"), ord("."), ord("("), ord(")"))):
        raise ValueError()

    return char


def _get_char_range(char_stream):
    while True:
        x = char_stream.peek_char()

        if x == ord("]"):
            return None
        else:
            char_stream.discard_char()

            if x == ord("\\"):
                x = char_stream.get_char()

                if not x in (ord("-"), ord("["), ord("]")):
                    return "\\" + chr(x)
            else:
                if x in (ord("-"), ord("["), ord("]")):
                    raise ValueError()

            y = char_stream.peek_char()

            if y == ord("-"):
                char_stream.discard_char()
                y = char_stream.get_char()

                if y == ord("\\"):
                    y = char_stream.get_char()

                    if not y in (ord("-"), ord("["), ord("]")):
                        raise ValueError()
                else:
                    if y in (ord("-"), ord("["), ord("]")):
                        raise ValueError()

                return (x, y)
            else:
                return chr(x)


def _expand_char_set(char_stream):
    char_set = []

    while True:
        char_range = _get_char_range(char_stream)

        if char_range is None:
            if len(char_set) == 0:
                raise ValueError()

            return "(" + "|".join(char_set) + ")"
        else:
            if len(char_range) == 1:
                char_set.append(char_range[0])
            else:
                for char in range(char_range[0], char_range[1] + 1):
                    char_set.append(chr(char))


def _preprocess_re(re):
    output = ""
    char_stream = _CharStream(re)

    while True:
        char = char_stream.peek_char()

        if char is None:
            return output
        else:
            char_stream.discard_char()

            if char == ord("\\"):
                char = char_stream.get_char()

                if char in (ord("["), ord("]")):
                    output += chr(char)
                else:
                    output += "\\" + chr(char)
            else:
                if char == ord("["):
                    output += _expand_char_set(char_stream)
                    char_stream.discard_char()
                elif char == ord("]"):
                    raise ValueError()
                else:
                    output += chr(char)


def _parse_state0(char_stream, next_state_slots):
    char = char_stream.peek_char()

    if char is None or char == ord(")"):
        return None
    else:
        char_stream.discard_char()

        if char == ord("\\"):
            char_was_escaped = True
            char = _unescape_char(char_stream)
        else:
            char_was_escaped = False

            if _is_meta_char(char):
                raise ValueError()

        if char == ord("(") and not char_was_escaped:
            state = _parse_state3(char_stream, next_state_slots)

            if char_stream.get_char() != ord(")"):
                raise ValueError()

            if state is None:
                raise ValueError()
        else:
            if char == ord(".") and not char_was_escaped:
                state_type = _STATE_TYPE_ANYCHAR
            else:
                state_type = char

            state = {"type": state_type}
            next_state_slots.append((state, "next"))

        return state


def _parse_state1(char_stream, next_state_slots):
    next_state_slots1 = []
    state1 = _parse_state0(char_stream, next_state_slots1)

    if state1 is None:
        return None
    else:
        char = char_stream.peek_char()

        if char == ord("?"):
            char_stream.discard_char()
            state2 = {"type": _STATE_TYPE_SPLIT, "next1": state1}
            next_state_slots.extend(next_state_slots1)
            next_state_slots.append((state2, "next2"))
            return state2
        elif char in (ord("+"), ord("*")):
            char_stream.discard_char()
            state2 = {"type": _STATE_TYPE_SPLIT, "next1": state1}

            for next_state_slot in next_state_slots1:
                next_state_slot[0][next_state_slot[1]] = state2

            next_state_slots.append((state2, "next2"))

            if char == ord("+"):
                return state1
            else:
                return state2
        else:
            next_state_slots.extend(next_state_slots1)
            return state1


def _parse_state2(char_stream, next_state_slots):
    next_state_slots1 = []
    state1 = _parse_state1(char_stream, next_state_slots1)

    if state1 is None:
        return None
    else:
        char = char_stream.peek_char()

        if char == ord("|"):
            next_state_slots.extend(next_state_slots1)
            return state1
        else:
            next_state_slots2 = []
            state2 = _parse_state2(char_stream, next_state_slots2)

            if state2 is None:
                next_state_slots.extend(next_state_slots1)
                return state1
            else:
                for next_state_slot in next_state_slots1:
                    next_state_slot[0][next_state_slot[1]] = state2

                next_state_slots.extend(next_state_slots2)
                return state1


def _parse_state3(char_stream, next_state_slots):
    next_state_slots1 = []
    state1 = _parse_state2(char_stream, next_state_slots1)

    if state1 is None:
        return None
    else:
        char = char_stream.peek_char()

        if char == ord("|"):
            char_stream.discard_char()
            next_state_slots2 = []
            state2 = _parse_state3(char_stream, next_state_slots2)

            if state2 is None:
                raise ValueError()

            state3 = {"type": _STATE_TYPE_SPLIT, "next1": state1, "next2": state2}
            next_state_slots.extend(next_state_slots1)
            next_state_slots.extend(next_state_slots2)
            return state3
        else:
            next_state_slots.extend(next_state_slots1)
            return state1


def _re2nfa(re):
    re = _preprocess_re(re)
    char_stream = _CharStream(re)
    next_state_slots1 = []
    state1 = _parse_state3(char_stream, next_state_slots1)

    if not char_stream.peek_char() is None:
        raise ValueError()

    if state1 is None:
        raise ValueError()

    state2 = {"type": _STATE_TYPE_MATCH}

    for next_state_slot in next_state_slots1:
        next_state_slot[0][next_state_slot[1]] = state2

    return state1


def _add_state(states, state, match_length):
    if "list_id" in state and state["list_id"] == _state_list_id:
        if state["match_length"] < match_length:
            state["match_length"] = match_length

            if state["type"] == _STATE_TYPE_SPLIT:
                _add_state(states, state["next1"], match_length)
                _add_state(states, state["next2"], match_length)
    else:
        state["list_id"] = _state_list_id
        state["match_length"] = match_length

        if state["type"] == _STATE_TYPE_SPLIT:
            _add_state(states, state["next1"], match_length)
            _add_state(states, state["next2"], match_length)
        else:
            states.append(state)


def _feed_char(input_states, output_states, char):
    global _state_list_id
    _state_list_id += 1

    match_lengths = []

    for input_state in input_states:
        if input_state["type"] in (char, _STATE_TYPE_ANYCHAR):
            match_lengths.append(input_state["match_length"])

    i = 0

    for input_state in input_states:
        if input_state["type"] in (char, _STATE_TYPE_ANYCHAR):
            _add_state(output_states, input_state["next"], match_lengths[i] + 1)
            i += 1


def _make_input_states(state):
    global _state_list_id

    input_states = []
    _state_list_id += 1
    _add_state(input_states, state, 0)
    return input_states


def match(re, string):
    state = _re2nfa(re)
    input_states = _make_input_states(state)

    for c in string:
        output_states = []
        _feed_char(input_states, output_states, ord(c))
        input_states = output_states

    for input_state in input_states:
        if input_state["type"] == _STATE_TYPE_MATCH:
            return True

    return False


def search(re, string):
    state = _re2nfa(re)
    input_states = _make_input_states(state)
    first_match_length = 0
    first_match_position = len(string)
    i = 0

    while True:
        for input_state in input_states:
            if input_state["type"] == _STATE_TYPE_MATCH:
                match_length = input_state["match_length"]
                match_position = i - match_length

                if match_position <= first_match_position:
                    first_match_length = match_length
                    first_match_position = match_position

        if i == len(string):
            break
        else:
            c = string[i]
            i += 1
            output_states = []
            _feed_char(input_states, output_states, ord(c))
            _add_state(output_states, state, 0)
            input_states = output_states

    return string[first_match_position:first_match_position + first_match_length]
