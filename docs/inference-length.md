# Inference length

[Feature index](README.md)

Choose **Inference length** before submitting a render:

| Mode | What it processes |
| --- | --- |
| Full shot | The entire source video; this is the default. |
| Frame count | The first N frames. Enter a positive whole number. |
| Seconds | The first N seconds. Enter a positive duration. |

Limited runs start at the beginning of the shot. Seconds are converted using the selected source's frame rate and rounded up to a whole frame. Requests longer than the source stop at its end.

Settings persist per project. Each render records its selected length in the result card and processing log. [PNG hint positions](png-hints.md) must fall within that range.
