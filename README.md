# claude-skills

Skills for [Claude Code](https://claude.com/claude-code): instructions, scripts and reference code that Claude
loads when a task calls for them.

| Skill | Use it for |
|---|---|
| [`phone-portal-reel`](skills/phone-portal-reel/SKILL.md) | A 9-second vertical product reel. A hand swipes a phone, and each product falls out of the screen onto a shelf, on the beat. Then comes a stop-motion shuffle of the line and a logo hold. There is no camera footage: the set and hands come from generated stills, and the product is a real 3D model |

## Install

As a Claude Code plugin:

```text
/plugin marketplace add vitozev/claude-skills
/plugin install vitozev-skills@vitozev
```

Or copy one skill into your personal skills folder:

```bash
git clone https://github.com/vitozev/claude-skills.git
```

```bash
cp -R claude-skills/skills/phone-portal-reel ~/.claude/skills/
```

Then ask for what the skill does, for example "make a phone-portal reel for my candle brand".

## What `phone-portal-reel` needs

- An OpenAI API key with image access (`gpt-image-2`, `gpt-image-1.5`)
- An ElevenLabs API key (music and sound effects)
- [HyperFrames](https://hyperframes.heygen.com) (`npx hyperframes`), three.js r169 and ffmpeg
- Python 3 with `numpy`, `opencv-python-headless`, `pillow` and `openai`

The scripts read keys from the environment or from a `.env` above the working folder, and they never print them.
They log what each run spends.

## License

MIT
