/**
 * SMarTrPlay — Xtream Codes API Client
 * Supports: get_live_categories, get_live_streams, get_vod_categories,
 *          get_vod_streams, get_series_categories, get_series
 */

const XtreamAPI = (function () {

  /**
   * Build Xtream API base URL
   * @param {string} server - Server URL (e.g., http://example.com:8080)
   * @param {string} username
   * @param {string} password
   * @returns {string} Base API URL
   */
  function buildBaseUrl(server, username, password) {
    const base = server.replace(/\/+$/, '');
    return `${base}/player_api.php?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`;
  }

  /**
   * Generic API call
   */
  async function apiCall(server, username, password, params = {}) {
    let url = buildBaseUrl(server, username, password);
    for (const [key, value] of Object.entries(params)) {
      url += `&${key}=${encodeURIComponent(value)}`;
    }

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Accept': 'application/json', 'User-Agent': 'SMarTrPlay/1.0' },
        timeout: 15000
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('XtreamAPI error:', error);
      throw error;
    }
  }

  /**
   * Get account info / authenticate
   */
  async function getAccountInfo(server, username, password) {
    return apiCall(server, username, password);
  }

  /**
   * Get Live TV categories
   */
  async function getLiveCategories(server, username, password) {
    return apiCall(server, username, password, { action: 'get_live_categories' });
  }

  /**
   * Get Live TV streams for a category
   * @param {string|null} categoryId - Category ID or null for all
   */
  async function getLiveStreams(server, username, password, categoryId = null) {
    const params = { action: 'get_live_streams' };
    if (categoryId) params.category_id = categoryId;
    return apiCall(server, username, password, params);
  }

  /**
   * Get VOD (Movies) categories
   */
  async function getVodCategories(server, username, password) {
    return apiCall(server, username, password, { action: 'get_vod_categories' });
  }

  /**
   * Get VOD streams for a category
   */
  async function getVodStreams(server, username, password, categoryId = null) {
    const params = { action: 'get_vod_streams' };
    if (categoryId) params.category_id = categoryId;
    return apiCall(server, username, password, params);
  }

  /**
   * Get Series categories
   */
  async function getSeriesCategories(server, username, password) {
    return apiCall(server, username, password, { action: 'get_series_categories' });
  }

  /**
   * Get Series for a category
   */
  async function getSeries(server, username, password, categoryId = null) {
    const params = { action: 'get_series' };
    if (categoryId) params.category_id = categoryId;
    return apiCall(server, username, password, params);
  }

  /**
   * Get series info (seasons & episodes)
   */
  async function getSeriesInfo(server, username, password, seriesId) {
    return apiCall(server, username, password, { action: 'get_series_info', series_id: seriesId });
  }

  /**
   * Get VOD info (movie details)
   */
  async function getVodInfo(server, username, password, vodId) {
    return apiCall(server, username, password, { action: 'get_vod_info', vod_id: vodId });
  }

  /**
   * Get Live Stream URL
   */
  function getLiveStreamUrl(server, username, password, streamId, extension = 'm3u8') {
    const base = server.replace(/\/+$/, '');
    return `${base}/live/${username}/${password}/${streamId}.${extension}`;
  }

  /**
   * Get VOD Stream URL
   */
  function getVodStreamUrl(server, username, password, streamId, extension = 'mp4') {
    const base = server.replace(/\/+$/, '');
    return `${base}/movie/${username}/${password}/${streamId}.${extension}`;
  }

  /**
   * Get Series Episode URL
   */
  function getSeriesEpisodeUrl(server, username, password, episodeId, extension = 'mp4') {
    const base = server.replace(/\/+$/, '');
    return `${base}/series/${username}/${password}/${episodeId}.${extension}`;
  }

  /**
   * Build stream URL from stream object
   */
  function buildStreamUrl(server, username, password, stream, type = 'live') {
    if (stream.stream_url && stream.stream_url.length > 0) {
      return stream.stream_url;
    }
    const streamId = stream.stream_id || stream.series_id || stream.vod_id;
    if (!streamId) return null;

    switch (type) {
      case 'live':
        return getLiveStreamUrl(server, username, password, streamId);
      case 'vod':
        return getVodStreamUrl(server, username, password, streamId);
      case 'series':
        return getSeriesEpisodeUrl(server, username, password, streamId);
      default:
        return getLiveStreamUrl(server, username, password, streamId);
    }
  }

  return {
    getAccountInfo,
    getLiveCategories,
    getLiveStreams,
    getVodCategories,
    getVodStreams,
    getSeriesCategories,
    getSeries,
    getSeriesInfo,
    getVodInfo,
    getLiveStreamUrl,
    getVodStreamUrl,
    getSeriesEpisodeUrl,
    buildStreamUrl
  };
})();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = XtreamAPI;
}
