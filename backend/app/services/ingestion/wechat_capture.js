async page => {
    const url = new URL(page.url());
    const article = /^\/s\/([A-Za-z0-9_-]+)$/.exec(url.pathname);
    if (url.origin !== 'https://mp.weixin.qq.com' || !article) {
        throw new Error('Open a public WeChat article short link first.');
    }

    const { title, publisher, content, publication } = await page.evaluate(() => {
        const text = selector => document.querySelector(selector)?.innerText.trim();
        return {
            title: text('#activity-name'),
            publisher: text('#js_name'),
            content: text('#js_content'),
            publication: text('#publish_time'),
        };
    });
    if (!title || !publisher || !content) {
        throw new Error('The article text is unavailable in this tab.');
    }

    const timestamp = /^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})$/.exec(
        publication ?? '',
    );
    let publishedAt = null;
    if (timestamp) {
        const [, year, month, day, hour, minute] = timestamp;
        const pad = value => value.padStart(2, '0');
        publishedAt = `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${minute}:00+08:00`;
    }
    return {
        platform: 'wechat',
        source_id: article[1],
        source_url: url.origin + url.pathname,
        source_name: publisher,
        title,
        content,
        fetched_at: new Date().toISOString(),
        published_at: publishedAt,
        raw_payload: { published_text: publication ?? null },
    };
}
