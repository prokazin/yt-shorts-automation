/**
 * Cloudflare Worker — планировщик (3 запуска в день).
 * Вызывает Render-бэкенд по расписанию.
 */

const BACKEND_URL = "https://ВАШ-СЕРВИС.onrender.com";

export default {
  async scheduled(event, env, ctx) {
    const payloads = [
      {
        query: "atmospheric nature",
        mood: "calm",
        title: "Атмосферная нарезка",
        description: "Успокаивающее видео с природой #shorts #atmospheric",
        tags: ["atmospheric", "nature", "relax", "shorts"],
      },
      {
        query: "vintage city 1950s",
        mood: "nostalgic",
        title: "Ретро-город",
        description: "Винтажные кадры города #shorts #retro #vintage",
        tags: ["retro", "vintage", "city", "shorts"],
      },
      {
        query: "ocean waves sunset",
        mood: "peaceful",
        title: "Океан на закате",
        description: "Волны и закат #shorts #ocean #sunset",
        tags: ["ocean", "sunset", "waves", "shorts"],
      },
    ];

    const hour = new Date(event.scheduledTime).getUTCHours();
    const index = hour < 12 ? 0 : hour < 18 ? 1 : 2;
    const payload = payloads[index];

    try {
      const response = await fetch(`${BACKEND_URL}/run-pipeline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      console.log(`[worker] Pipeline: ${JSON.stringify(result)}`);
    } catch (error) {
      console.error(`[worker] Ошибка: ${error.message}`);
    }
  },
};
