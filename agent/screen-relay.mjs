const PATH_PATTERN = /^relink-[a-f0-9]{32}$/;
const CONNECTION_PATTERN =
  /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;

/** MediaMTX control stays on loopback; credentials never appear in errors. */
export function createMediaMtxRelay({
  apiUrl = "http://127.0.0.1:9997",
  host,
  port = 8890,
}) {
  const control = new URL(apiUrl);
  if (
    control.protocol !== "http:" ||
    !["127.0.0.1", "[::1]"].includes(control.hostname) ||
    control.username ||
    control.password ||
    control.pathname !== "/" ||
    control.search ||
    control.hash
  ) {
    throw new Error(
      "Screen relay Control API must be an HTTP loopback origin.",
    );
  }
  if (
    typeof host !== "string" ||
    !/^[a-zA-Z0-9.-]{1,253}$/.test(host) ||
    !Number.isInteger(port) ||
    port < 1 ||
    port > 65535
  )
    throw new Error("Invalid screen relay host or port.");

  async function request(method, path, body) {
    let response;
    try {
      response = await fetch(new URL(path, control), {
        method,
        signal: AbortSignal.timeout(3000),
        ...(body
          ? {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            }
          : {}),
      });
      const text = await response.text();
      if (text.length > 1024 * 1024) throw new Error("Oversized response");
      return { status: response.status, data: text ? JSON.parse(text) : null };
    } catch {
      throw new Error("Screen relay Control API is unavailable.");
    }
  }

  function requireSuccess(result) {
    if (result.status < 200 || result.status >= 300)
      throw new Error("Screen relay rejected the requested operation.");
    return result.data;
  }
  function validPath(path) {
    if (!PATH_PATTERN.test(path))
      throw new Error("Invalid Relink screen path.");
    return path;
  }
  async function list(endpoint) {
    const items = [];
    for (let page = 0; page < 20; page += 1) {
      const data = requireSuccess(
        await request("GET", `${endpoint}?itemsPerPage=100&page=${page}`),
      );
      if (!data || !Array.isArray(data.items))
        throw new Error("Invalid screen relay response.");
      items.push(...data.items);
      if (
        data.items.length < 100 ||
        (Number.isInteger(data.pageCount) && page + 1 >= data.pageCount)
      )
        return items;
    }
    throw new Error("Screen relay inventory exceeds the inspection limit.");
  }

  return {
    host,
    port,
    async createPath(path, publishPassphrase, readPassphrase) {
      requireSuccess(
        await request("POST", `/v3/config/paths/add/${validPath(path)}`, {
          source: "publisher",
          sourceOnDemand: false,
          maxReaders: 8, // Seven Room viewers plus one loopback quality probe.
          overridePublisher: false,
          record: false,
          srtPublishPassphrase: publishPassphrase,
          srtReadPassphrase: readPassphrase,
        }),
      );
    },
    async deletePath(path) {
      const result = await request(
        "DELETE",
        `/v3/config/paths/delete/${validPath(path)}`,
      );
      if (result.status !== 404) requireSuccess(result);
    },
    async isPathReady(path, { includeSystemAudio = false, kind } = {}) {
      const result = await request("GET", `/v3/paths/get/${validPath(path)}`);
      if (result.status === 404) return false;
      const state = requireSuccess(result);
      if (!state?.ready) return false;
      if (kind === "audio")
        return (
          Array.isArray(state.tracks) &&
          state.tracks.length === 1 &&
          typeof state.tracks[0] === "string" &&
          ["mpeg4audio", "aac"].includes(
            state.tracks[0].toLowerCase().replace(/[^a-z0-9]/g, ""),
          )
        );
      if (!includeSystemAudio) return true;
      return (
        Array.isArray(state.tracks) &&
        state.tracks.some(
          (track) =>
            typeof track === "string" &&
            ["mpeg4audio", "aac"].includes(
              track.toLowerCase().replace(/[^a-z0-9]/g, ""),
            ),
        )
      );
    },
    async listPaths() {
      return (await list("/v3/config/paths/list"))
        .filter(
          (item) =>
            typeof item.name === "string" && PATH_PATTERN.test(item.name),
        )
        .map((item) => item.name);
    },
    async listConnections() {
      return (await list("/v3/srtconns/list"))
        .filter(
          (item) =>
            typeof item.path === "string" &&
            PATH_PATTERN.test(item.path) &&
            typeof item.id === "string" &&
            CONNECTION_PATTERN.test(item.id),
        )
        .map((item) => ({ id: item.id, path: item.path, state: item.state, ...(Number.isSafeInteger(item.bytesSent) && item.bytesSent >= 0 ? {bytesSent:item.bytesSent} : {}) }));
    },
    async kickConnection(id) {
      if (!CONNECTION_PATTERN.test(id))
        throw new Error("Invalid screen relay connection ID.");
      const result = await request("POST", `/v3/srtconns/kick/${id}`);
      if (result.status !== 404) requireSuccess(result);
    },
  };
}
