# Event Schema

All events are single-line JSON objects. The addon emits them to chat with the
prefix `ASCIIMUD|` so the companion can filter them out of the rest of the chat
log.

```
ASCIIMUD|{"t":"snapshot","data":{...}}
ASCIIMUD|{"t":"severity","level":3}
ASCIIMUD|{"t":"death","player":"Steven"}
```

The companion strips the prefix and rebroadcasts the JSON object verbatim over
the WebSocket.

## Envelope

| Field | Type   | Required | Notes                                         |
| ----- | ------ | -------- | --------------------------------------------- |
| `t`   | string | yes      | Event type discriminator.                     |

## Types

### `snapshot`

The full canonical world state. Sent up to 2 Hz (rate-limited in the addon).

```json
{
  "t": "snapshot",
  "data": {
    "v": 1,
    "tick": 1234,
    "combat": false,
    "chapter": 1,
    "player": { "name": "Steven", "class": "WARLOCK", "level": 12,
                "hp": 320, "hpMax": 360, "mp": 180, "mpMax": 200 },
    "zone":   { "name": "Elwynn Forest", "subzone": "Goldshire", "x": 0, "y": 0 },
    "target": { "name": "Defias Thug", "level": 11, "hp": 80, "hpMax": 120,
                "hostile": true }
  }
}
```

`target` is `null` when nothing is targeted.

### `severity`

```json
{ "t": "severity", "level": 0 }
```

`level` is an integer 0–5. Decays over time, spikes on threat events.

### `death`

```json
{ "t": "death", "player": "Steven" }
```

## Forward compatibility

Consumers MUST ignore unknown event types and unknown fields. Schema is
versioned via `data.v` inside `snapshot`; bump on breaking changes.
