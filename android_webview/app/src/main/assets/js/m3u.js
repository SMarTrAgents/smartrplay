/**
 * SMarTrPlay — M3U / M3U+ Parser
 * Parses M3U and M3U+ playlists with #EXTINF attributes
 */

const M3UParser = (function () {

  /**
   * Parse M3U/M3U+ content
   * @param {string} content - Raw M3U file content
   * @returns {object} { groups: {}, channels: [] }
   */
  function parse(content) {
    const lines = content.split(/\r?\n/);
    const channels = [];
    let currentEntry = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.startsWith('#EXTM3U')) {
        // Header — skip
        continue;
      }

      if (line.startsWith('#EXTINF')) {
        currentEntry = parseExtInf(line);
        continue;
      }

      // Skip other directives
      if (line.startsWith('#') && !line.startsWith('#EXTINF')) {
        // Could be #EXTGRP, #EXTVLCOPT, etc.
        if (line.startsWith('#EXTGRP:')) {
          if (currentEntry) {
            currentEntry.group = line.substring(8).trim();
          }
        }
        continue;
      }

      // URL line (non-empty, non-comment)
      if (line && !line.startsWith('#') && currentEntry) {
        currentEntry.url = line;
        channels.push(currentEntry);
        currentEntry = null;
      } else if (line && !line.startsWith('#') && !currentEntry) {
        // URL without EXTINF — create minimal entry
        channels.push({
          name: 'Unknown',
          url: line,
          logo: '',
          group: 'Ungrouped',
          tvgId: '',
          tvgName: '',
          tvgLogo: ''
        });
      }
    }

    // Group channels by category
    const groups = {};
    for (const ch of channels) {
      const group = ch.group || 'Ungrouped';
      if (!groups[group]) groups[group] = [];
      groups[group].push(ch);
    }

    return { channels, groups };
  }

  /**
   * Parse #EXTINF line
   * Format: #EXTINF:duration [key="value" ...],channel name
   */
  function parseExtInf(line) {
    const entry = {
      name: '',
      logo: '',
      group: 'Ungrouped',
      tvgId: '',
      tvgName: '',
      tvgLogo: '',
      duration: -1
    };

    // Remove #EXTINF:
    const content = line.substring(8);

    // Split by first comma — everything before is attributes, after is name
    const commaIdx = content.indexOf(',');
    if (commaIdx === -1) {
      entry.name = content.trim();
      return entry;
    }

    const attrPart = content.substring(0, commaIdx);
    const namePart = content.substring(commaIdx + 1).trim();

    entry.name = namePart;

    // Parse duration (first number)
    const durationMatch = attrPart.match(/^(\-?\d+(?:\.\d+)?)/);
    if (durationMatch) {
      entry.duration = parseFloat(durationMatch[1]);
    }

    // Parse key="value" attributes
    const attrRegex = /([a-zA-Z0-9_-]+)="([^"]*)"/g;
    let match;
    while ((match = attrRegex.exec(attrPart)) !== null) {
      const key = match[1].toLowerCase();
      const value = match[2];

      switch (key) {
        case 'tvg-id':
          entry.tvgId = value;
          break;
        case 'tvg-name':
          entry.tvgName = value;
          break;
        case 'tvg-logo':
          entry.tvgLogo = value;
          entry.logo = value;
          break;
        case 'group-title':
          entry.group = value;
          break;
        case 'logo':
          entry.logo = value;
          break;
      }
    }

    return entry;
  }

  /**
   * Fetch and parse M3U from URL
   * @param {string} url - M3U playlist URL
   * @returns {Promise<object>} Parsed playlist
   */
  async function fetchAndParse(url) {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'User-Agent': 'SMarTrPlay/1.0' },
        timeout: 30000
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const content = await response.text();
      return parse(content);
    } catch (error) {
      console.error('M3U fetch error:', error);
      throw error;
    }
  }

  /**
   * Filter channels by group
   */
  function filterByGroup(channels, groupName) {
    return channels.filter(ch => (ch.group || 'Ungrouped') === groupName);
  }

  /**
   * Search channels by name
   */
  function searchChannels(channels, query) {
    const lowerQuery = query.toLowerCase();
    return channels.filter(ch =>
      ch.name.toLowerCase().includes(lowerQuery)
    );
  }

  return {
    parse,
    fetchAndParse,
    filterByGroup,
    searchChannels
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = M3UParser;
}
