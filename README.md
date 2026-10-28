# YT-Video-Editor

Professional AI-powered video editing project for YouTube.

## Project Description
Cloud-based video editing using OpenAI Codex.

## Tools
- FFmpeg
- Python
- Remotion (optional)

## Features
- Combine multiple videos into one
- Professional video transitions
- Color correction
- Audio enhancement and noise reduction
- Preserve original conversations
- Add titles and subtitles
- Automatic video editing
- Export finished videos

## Video Settings
- Format: MP4
- Resolution: 1920x1080 (Full HD)
- Aspect Ratio: 16:9
- Video Codec: H.264
- Audio Codec: AAC

## Goal
Create professional, high-quality, long-form
YouTube videos using AI-assisted editing.

## Автоматичний монтаж

Потрібні Python 3.10+ та FFmpeg/FFprobe із кодеком `libx264`. Зовнішні
Python-пакети та API-ключі не потрібні. У хмарному середовищі перевірено
Python 3.12.14 та FFmpeg/FFprobe 7.1.5.

Структура:
- `input/` — вихідні відео;
- `output/` — готові MP4;
- `temp/` — ізольовані тимчасові матеріали, автоматично видаляються після запуску;
- `scripts/` — монтаж і синтетична перевірка.

Із кореня репозиторію:

```bash
python3 --version
ffmpeg -version
ffprobe -version
cp edit.example.json edit.local.json
# Відредагуйте edit.local.json перед запуском на власних матеріалах.
python3 scripts/edit.py edit.local.json
```

У `clips` задайте порядок файлів і ділянки, які потрібно **залишити**:
`start` включно, `end` виключно, у секундах. Без цих полів використовується
весь кліп. Щоб прибрати середину розмови, додайте дві збережені ділянки
того самого файлу окремими елементами. Автоматичного розпізнавання змісту,
тиші чи небажаних фрагментів немає.

Шляхи відео та результату відносні до кореня проєкту; також підтримуються
абсолютні шляхи. Файл результату повинен бути новим: перезапис заборонено.
`transition_seconds` задає плавний відеоперехід і змішування звуку;
`0` означає звичайну склейку. За наявності переходів кожна ділянка має бути
довшою за подвійну тривалість переходу. Перехід скорочує загальну тривалість
на свою тривалість для кожного стику. Щоб не змішувати слова на стиках
розмов, використовуйте `transition_seconds: 0` або обирайте паузи.

`brightness`, `contrast`, `saturation` керують загальною кольорокорекцією.
Оригінальний звук зберігається без заміни музикою чи видалення розмов;
гучність обробляється однопрохідним `loudnorm` із ціллю -16 LUFS / -1.5 dBTP.
Це не гарантує точного виміряного LUFS кожного результату. Кліпи без звуку
отримують тишу. Експорт: MP4, H.264/yuv420p, AAC stereo 48 kHz, 1920×1080,
30 FPS. Пропорції джерела зберігаються з полями, без розтягування.

Для довгих відео передбачте місце для нормалізованих копій усіх кліпів
і готового результату. Кодування використовує два потоки; `preset` і `crf`
керують швидкістю та якістю. Обробка локальна, без завантаження в YouTube.

## Синтетична перевірка

```bash
python3 scripts/smoke_test.py
ffprobe -v error -show_streams -show_format -of json output/test_5s.mp4
```

Перевірка створює `output/test_5s.mp4` винятково з генераторів FFmpeg:
5 секунд, 1920×1080, 30 FPS, H.264/AAC. Додатково запускає справжній монтаж
із переходом, обрізанням, корекцією кольору, нормалізацією звуку, тихим
кліпом, звичайною склейкою та одним кліпом. Перевіряє метадані, тривалість,
повне декодування і захист від перезапису. Для повторного запуску спершу
перемістіть або видаліть лише створений тестовий `output/test_5s.mp4`.
Реальні матеріали тест не читає. Відео і тимчасові файли ігноруються Git.
