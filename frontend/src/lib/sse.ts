import type { SseEvent } from "../types";

export async function* parseSseStream(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const emitBlock = (block: string): SseEvent | null => {
    const trimmed = block.trim();
    if (!trimmed) {
      return null;
    }

    let event = "message";
    const dataLines: string[] = [];

    for (const line of trimmed.split(/\r?\n/)) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
        continue;
      }

      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^\s/, ""));
      }
    }

    return {
      event,
      data: dataLines.join("\n")
    };
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const event = emitBlock(part);
      if (event) {
        yield event;
      }
    }
  }

  buffer += decoder.decode();
  const tail = emitBlock(buffer);
  if (tail) {
    yield tail;
  }
}

export function parseSseData(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }

  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    return trimmed;
  }
}
