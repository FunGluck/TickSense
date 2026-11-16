(async () => {
  try {
    const node = document.getElementById('report-data');
    const encoded = node.textContent;
    node.textContent = '';
    // Decode chunks into one byte buffer rather than retaining a second full binary string.
    const bytes = new Uint8Array(Math.floor(encoded.length * 3 / 4));
    let offset = 0;
    for (let start = 0; start < encoded.length; start += 65536) {
      const chunk = atob(encoded.slice(start, start + 65536));
      for (let i = 0; i < chunk.length; i++) bytes[offset++] = chunk.charCodeAt(i);
    }
    const stream = new Blob([bytes.subarray(0, offset)]).stream()
      .pipeThrough(new DecompressionStream('gzip'));
    const decodedReport = await new Response(stream).json();
    /*DASHBOARD*/
  } catch (error) {
    document.getElementById('analysis-conclusion').textContent =
      'Не удалось загрузить данные отчёта. Откройте файл в актуальном браузере с поддержкой gzip.';
    console.error(error);
  }
})()
