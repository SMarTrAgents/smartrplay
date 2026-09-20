/* ============================================================
   SMarTrPlay — Main App Logic
   Provider management, playlist loading, rendering, D-Pad nav
   Pure ES6+, Android WebView compatible
   ============================================================ */

'use strict';

// ================================================================
//  STATE
// ================================================================
const State = {
    providers: [],       // saved providers from localStorage
    activeProvider: null,// currently loaded provider object
    xtreamAPI: null,     // XtreamAPI instance when active
    currentTab: 'live',  // 'live' | 'vod' | 'series'
    categories: [],      // current categories for active tab
    activeCategory: null,// selected category ID
    channels: [],        // current loaded channels
    filteredChannels: [],// after search filter
    m3uGroups: {},      // for M3U: group -> channels map
    m3uGroupList: [],    // for M3U: ordered group names
    loading: false,
    searchQuery: ''
};

const STORAGE_KEY = 'smartrplay_providers';
const ACTIVE_KEY = 'smartrplay_active_provider';

// ================================================================
//  DOM REFERENCES
// ================================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    searchInput: $('#searchInput'),
    btnProviders: $('#btnProviders'),
    btnSettings: $('#btnSettings'),
    sidebar: $('#sidebar'),
    categoryList: $('#categoryList'),
    categoryTitle: $('#categoryTitle'),
    content: $('#content'),
    contentTitle: $('#contentTitle'),
    contentCount: $('#contentCount'),
    channelGrid: $('#channelGrid'),
    loading: $('#loading'),
    providerModal: $('#providerModal'),
    btnCloseModal: $('#btnCloseModal'),
    formXtream: $('#formXtream'),
    formM3u: $('#formM3u'),
    xtreamName: $('#xtreamName'),
    xtreamServer: $('#xtreamServer'),
    xtreamUser: $('#xtreamUser'),
    xtreamPass: $('#xtreamPass'),
    btnSaveXtream: $('#btnSaveXtream'),
    m3uName: $('#m3uName'),
    m3uUrl: $('#m3uUrl'),
    btnSaveM3u: $('#btnSaveM3u'),
    savedProvidersList: $('#savedProvidersList'),
    btnAddProviderEmpty: $('#btnAddProviderEmpty'),
    btnAddProviderWelcome: $('#btnAddProviderWelcome'),
    toast: $('#toast')
};

// ================================================================
//  TOAST
// ================================================================
let toastTimer = null;
function showToast(msg, type = 'info') {
    if (!dom.toast) return;
    dom.toast.textContent = msg;
    dom.toast.className = 'smt-toast show ' + type;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        dom.toast.className = 'smt-toast ' + type;
    }, 3000);
}

// ================================================================
//  PROVIDER MANAGEMENT (localStorage)
// ================================================================
function loadProviders() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        State.providers = raw ? JSON.parse(raw) : [];
    } catch (e) {
        State.providers = [];
    }
}

function saveProviders() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(State.providers));
}

function getActiveProviderId() {
    return localStorage.getItem(ACTIVE_KEY);
}

function setActiveProviderId(id) {
    if (id) {
        localStorage.setItem(ACTIVE_KEY, id);
    } else {
        localStorage.removeItem(ACTIVE_KEY);
    }
}

function addProvider(provider) {
    provider.id = 'prov_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    provider.created = Date.now();
    State.providers.push(provider);
    saveProviders();
    return provider;
}

function deleteProvider(id) {
    State.providers = State.providers.filter(p => p.id !== id);
    saveProviders();
    if (getActiveProviderId() === id) {
        setActiveProviderId(null);
        State.activeProvider = null;
        State.xtreamAPI = null;
        resetContent();
    }
    renderSavedProviders();
}

function findProvider(id) {
    return State.providers.find(p => p.id === id);
}

// ================================================================
//  RENDER SAVED PROVIDERS LIST
// ================================================================
function renderSavedProviders() {
    if (!dom.savedProvidersList) return;
    if (State.providers.length === 0) {
        dom.savedProvidersList.innerHTML = '<p class="smt-saved-empty">Keine Provider gespeichert</p>';
        return;
    }

    dom.savedProvidersList.innerHTML = State.providers.map(p => {
        const typeLabel = p.type === 'xtream' ? 'Xtream Codes' : 'M3U Playlist';
        const isActive = getActiveProviderId() === p.id;
        return `
            <div class="smt-saved-item" tabindex="0" data-provider-id="${p.id}">
                <div class="smt-saved-item-info">
                    <div class="smt-saved-item-name">${escapeHtml(p.name)}${isActive ? ' <span style="color:var(--accent-cyan)">●</span>' : ''}</div>
                    <div class="smt-saved-item-type">${typeLabel}${p.type === 'xtream' ? ' — ' + escapeHtml(p.server) : ''}</div>
                </div>
                <div class="smt-saved-item-actions">
                    <button class="smt-icon-btn" onclick="activateProvider('${p.id}')" tabindex="0">Laden</button>
                    <button class="smt-icon-btn danger" onclick="deleteProvider('${p.id}')" tabindex="0">Löschen</button>
                </div>
            </div>
        `;
    }).join('');
}

// ================================================================
//  ESCAPE HTML
// ================================================================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ================================================================
//  MODAL
// ================================================================
function openProviderModal() {
    dom.providerModal.classList.add('active');
    renderSavedProviders();
    // focus first tab
    setTimeout(() => {
        const firstTab = dom.providerModal.querySelector('.smt-provider-tab.active');
        if (firstTab) firstTab.focus();
    }, 100);
}

function closeProviderModal() {
    dom.providerModal.classList.remove('active');
}

// ================================================================
//  TABS (Live / VOD / Series)
// ================================================================
function switchTab(tabName) {
    State.currentTab = tabName;
    State.activeCategory = null;
    State.searchQuery = '';
    if (dom.searchInput) dom.searchInput.value = '';

    $$('.smt-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    if (State.activeProvider) {
        if (State.activeProvider.type === 'xtream') {
            loadXtreamCategories();
        } else {
            renderM3uCategories();
        }
    }
}

// ================================================================
//  LOAD XTREAM CATEGORIES
// ================================================================
async function loadXtreamCategories() {
    if (!State.xtreamAPI) return;
    showLoading(true);
    try {
        let cats = [];
        switch (State.currentTab) {
            case 'live':
                cats = await State.xtreamAPI.get_live_categories();
                dom.categoryTitle.textContent = 'Live TV Kategorien';
                dom.contentTitle.textContent = 'Live TV';
                break;
            case 'vod':
                cats = await State.xtreamAPI.get_vod_categories();
                dom.categoryTitle.textContent = 'Film Kategorien';
                dom.contentTitle.textContent = 'Filme';
                break;
            case 'series':
                cats = await State.xtreamAPI.get_series_categories();
                dom.categoryTitle.textContent = 'Serien Kategorien';
                dom.contentTitle.textContent = 'Serien';
                break;
        }
        State.categories = cats || [];
        renderCategoryList(cats || []);

        // Auto-load first category or all streams
        if (cats && cats.length > 0) {
            await selectCategory(cats[0].category_id);
        } else {
            // No categories — load all
            await selectCategory(null);
        }
    } catch (err) {
        showToast('Fehler beim Laden der Kategorien: ' + err.message, 'error');
        renderCategoryList([]);
    } finally {
        showLoading(false);
    }
}

// ================================================================
//  RENDER CATEGORY LIST
// ================================================================
function renderCategoryList(categories) {
    if (!dom.categoryList) return;
    if (!categories || categories.length === 0) {
        dom.categoryList.innerHTML = '<div class="smt-empty"><p>Keine Kategorien</p></div>';
        return;
    }

    // Add "All" option at top
    const allItem = `<button class="smt-category-item${State.activeCategory === null ? ' active' : ''}" tabindex="0" data-category-id="__all__">
            <span>Alle</span>
        </button>`;

    dom.categoryList.innerHTML = allItem + categories.map(cat => `
        <button class="smt-category-item${State.activeCategory === cat.category_id ? ' active' : ''}" tabindex="0" data-category-id="${escapeHtml(cat.category_id)}">
            <span>${escapeHtml(cat.category_name)}</span>
        </button>
    `).join('');

    // Attach click handlers
    dom.categoryList.querySelectorAll('.smt-category-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const catId = btn.dataset.categoryId;
            const realId = catId === '__all__' ? null : catId;
            selectCategory(realId);
        });
    });
}

// ================================================================
//  SELECT CATEGORY — LOAD STREAMS
// ================================================================
async function selectCategory(categoryId) {
    State.activeCategory = categoryId;

    // Update active styles
    $$('.smt-category-item').forEach(item => {
        const itemCatId = item.dataset.categoryId;
        const matches = categoryId === null ? itemCatId === '__all__' : itemCatId === categoryId;
        item.classList.toggle('active', matches);
    });

    if (!State.activeProvider) return;

    showLoading(true);
    try {
        if (State.activeProvider.type === 'xtream') {
            await loadXtreamStreams(categoryId);
        } else {
            loadM3uChannelsForCategory(categoryId);
        }
    } catch (err) {
        showToast('Fehler: ' + err.message, 'error');
    } finally {
        showLoading(false);
    }
}

// ================================================================
//  LOAD XTREAM STREAMS
// ================================================================
async function loadXtreamStreams(categoryId) {
    if (!State.xtreamAPI) return;
    let streams = [];

    switch (State.currentTab) {
        case 'live':
            streams = await State.xtreamAPI.get_live_streams(categoryId);
            break;
        case 'vod':
            streams = await State.xtreamAPI.get_vod_streams(categoryId);
            break;
        case 'series':
            streams = await State.xtreamAPI.get_series(categoryId);
            break;
    }

    State.channels = (streams || []).map(s => normalizeXtreamStream(s));
    State.filteredChannels = [...State.channels];
    renderChannels(State.filteredChannels);
}

// ================================================================
//  NORMALIZE XTREAM STREAM
// ================================================================
function normalizeXtreamStream(raw) {
    const isSeries = State.currentTab === 'series';
    const isVod = State.currentTab === 'vod';
    const streamId = raw.stream_id || raw.series_id || '';

    let url = '';
    let container = raw.container_extension || '';

    if (isSeries) {
        // Series needs series_info to get episode URLs
        // For now, link to a series detail page
        url = `series:${streamId}`;
    } else if (isVod) {
        url = State.xtreamAPI.vodStreamUrl(streamId, container || 'mp4');
    } else {
        // Live
        url = State.xtreamAPI.liveStreamUrl(streamId, '.ts');
    }

    return {
        id: streamId,
        name: raw.name || 'Unbekannt',
        logo: raw.stream_icon || raw.cover || '',
        group: '',
        url: url,
        type: State.currentTab,
        raw: raw
    };
}

// ================================================================
//  M3U: RENDER CATEGORIES (GROUPS)
// ================================================================
function renderM3uCategories() {
    const groups = State.m3uGroupList || [];
    const groupCounts = {};
    for (const g of groups) {
        groupCounts[g] = (State.m3uGroups[g] || []).length;
    }

    dom.categoryTitle.textContent = 'Gruppen';
    dom.contentTitle.textContent = 'Alle Kanäle';

    if (groups.length === 0) {
        dom.categoryList.innerHTML = '<div class="smt-empty"><p>Keine Gruppen</p></div>';
        return;
    }

    const allItem = `<button class="smt-category-item${State.activeCategory === null ? ' active' : ''}" tabindex="0" data-category-id="__all__">
        <span>Alle</span>
        <span class="smt-category-count">${State.channels.length}</span>
    </button>`;

    dom.categoryList.innerHTML = allItem + groups.map(g => `
        <button class="smt-category-item${State.activeCategory === g ? ' active' : ''}" tabindex="0" data-category-id="${escapeHtml(g)}">
            <span>${escapeHtml(g)}</span>
            <span class="smt-category-count">${groupCounts[g] || 0}</span>
        </button>
    `).join('');

    dom.categoryList.querySelectorAll('.smt-category-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const catId = btn.dataset.categoryId;
            const realId = catId === '__all__' ? null : catId;
            selectCategory(realId);
        });
    });

    // Load all channels initially
    loadM3uChannelsForCategory(null);
}

// ================================================================
//  M3U: FILTER BY CATEGORY/GROUP
// ================================================================
function loadM3uChannelsForCategory(groupId) {
    if (groupId === null || groupId === undefined) {
        State.filteredChannels = [...State.channels];
    } else {
        State.filteredChannels = (State.m3uGroups[groupId] || []).map(ch => ({
            ...ch,
            type: 'live'
        }));
    }
    renderChannels(State.filteredChannels);
}

// ================================================================
//  RENDER CHANNEL GRID
// ================================================================
function renderChannels(channels) {
    if (!dom.channelGrid) return;
    const count = channels.length;
    dom.contentCount.textContent = count > 0 ? `${count} Einträge` : '';

    if (count === 0) {
        dom.channelGrid.innerHTML = `
            <div class="smt-welcome" style="grid-column:1/-1;">
                <div class="smt-welcome-icon">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                </div>
                <h2>Keine Einträge gefunden</h2>
                <p>${State.searchQuery ? 'Keine Treffer für &quot;' + escapeHtml(State.searchQuery) + '&quot;' : 'Diese Kategorie ist leer'}</p>
            </div>
        `;
        return;
    }

    dom.channelGrid.innerHTML = channels.map((ch, idx) => {
        const logoHtml = ch.logo
n            ? `<img src="${escapeHtml(ch.logo)}" alt="" class="smt-channel-logo" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
               <div class="smt-channel-logo-placeholder" style="display:none;">${escapeHtml(getInitials(ch.name))}</div>`
            : `<div class="smt-channel-logo-placeholder">${escapeHtml(getInitials(ch.name))}</div>`;

        const groupName = ch.group || '';
        const streamUrl = ch.url || '';
        const streamName = ch.name || '';
        const isSeries = ch.type === 'series';

        return `
            <div class="smt-channel-card" tabindex="0" data-index="${idx}"
                 data-url="${escapeHtml(streamUrl)}"
                 data-name="${escapeHtml(streamName)}"
                 data-type="${ch.type || 'live'}"
                 data-id="${escapeHtml(ch.id || '')}"
                 onclick="playChannel(this)">
                ${logoHtml}
                <div class="smt-channel-info">
                    <div class="smt-channel-name">${escapeHtml(streamName)}</div>
                    ${groupName ? `<div class="smt-channel-group">${escapeHtml(groupName)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function getInitials(name) {
    if (!name) return '?';
    const words = name.trim().split(/\s+/);
    if (words.length === 1) return words[0].substring(0, 2).toUpperCase();
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

// ================================================================
//  PLAY CHANNEL — OPEN PLAYER
// ================================================================
function playChannel(card) {
    const url = card.dataset.url;
    const name = card.dataset.name;
    const type = card.dataset.type;
    const id = card.dataset.id;

    if (!url) {
        showToast('Keine Stream-URL verfügbar', 'error');
        return;
    }

    // Series: show series info page
    if (url.startsWith('series:')) {
        const seriesId = url.split(':')[1];
        openSeriesInfo(seriesId, name);
        return;
    }

    // Open player.html with stream URL
    const playerUrl = `player.html?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}&type=${type}`;
    window.location.href = playerUrl;
}

// ================================================================
//  SERIES INFO — LOAD EPISODES
// ================================================================
async function openSeriesInfo(seriesId, seriesName) {
    if (!State.xtreamAPI) return;
    showLoading(true);
    try {
        const info = await State.xtreamAPI.get_series_info(seriesId);
        if (!info || !info.episodes) {
            showToast('Keine Episoden gefunden', 'error');
            return;
        }

        // Render episode list in the channel grid
        const seasons = info.episodes || {};
        const episodes = [];
        for (const seasonKey of Object.keys(seasons)) {
            for (const ep of seasons[seasonKey]) {
                const container = ep.container_extension || 'mp4';
                const url = State.xtreamAPI.seriesStreamUrl(ep.id, container);
                episodes.push({
                    name: `${seriesName} — S${seasonKey}E${ep.episode_num || ep.id}: ${ep.title || ''}`,
                    url: url,
                    logo: info.info?.cover || info.cover || '',
                    group: `Season ${seasonKey}`,
                    type: 'series'
                });
            }
        }

        State.filteredChannels = episodes;
        dom.contentTitle.textContent = seriesName;
        renderChannels(episodes);
    } catch (err) {
        showToast('Fehler beim Laden der Serien: ' + err.message, 'error');
    } finally {
        showLoading(false);
    }
}

// ================================================================
//  SEARCH FILTER
// ================================================================
function applySearch(query) {
    State.searchQuery = query.toLowerCase().trim();
    if (!State.searchQuery) {
        State.filteredChannels = [...State.channels];
    } else {
        State.filteredChannels = State.channels.filter(ch => {
            return (ch.name && ch.name.toLowerCase().includes(State.searchQuery))
                || (ch.group && ch.group.toLowerCase().includes(State.searchQuery));
        });
    }
    renderChannels(State.filteredChannels);
}

// ================================================================
//  LOADING INDICATOR
// ================================================================
function showLoading(show) {
    State.loading = show;
    if (dom.loading) {
        dom.loading.style.display = show ? 'flex' : 'none';
    }
}

// ================================================================
//  RESET CONTENT
// ================================================================
function resetContent() {
    State.channels = [];
    State.filteredChannels = [];
    State.categories = [];
    State.activeCategory = null;
    State.m3uGroups = {};
    State.m3uGroupList = [];
    if (dom.categoryList) dom.categoryList.innerHTML = '';
    if (dom.channelGrid) {
        dom.channelGrid.innerHTML = `
            <div class="smt-welcome">
                <div class="smt-welcome-icon">
                    <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="2" y="3" width="20" height="14" rx="2"/>
                        <path d="M8 21h8M12 17v4"/>
                    </svg>
                </div>
                <h2>Willkommen bei SMarTrPlay</h2>
                <p>Fügen Sie einen Provider hinzu, um zu starten</p>
                <button class="smt-btn smt-btn-primary smt-btn-lg" id="btnAddProviderWelcome2" tabindex="0" onclick="openProviderModal()">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19"/>
                        <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    Provider hinzufügen
                </button>
            </div>
        `;
    }
    if (dom.contentCount) dom.contentCount.textContent = '';
}

// ================================================================
//  ACTIVATE PROVIDER — LOAD PLAYLIST
// ================================================================
async function activateProvider(id) {
    const provider = findProvider(id);
    if (!provider) {
        showToast('Provider nicht gefunden', 'error');
        return;
    }

    State.activeProvider = provider;
    setActiveProviderId(id);
    closeProviderModal();
    resetContent();
    showLoading(true);

    try {
        if (provider.type === 'xtream') {
            State.xtreamAPI = new XtreamAPI(provider.server, provider.user, provider.pass);
            // Authenticate
            const authInfo = await State.xtreamAPI.authenticate();
            if (!authInfo || authInfo.user_info?.auth === 0) {
                showToast('Login fehlgeschlagen — falsche Zugangsdaten', 'error');
                State.xtreamAPI = null;
                State.activeProvider = null;
                setActiveProviderId(null);
                showLoading(false);
                return;
            }
            showToast('Verbunden: ' + provider.name, 'success');
            await loadXtreamCategories();
        } else if (provider.type === 'm3u') {
            State.xtreamAPI = null;
            const channels = await fetch_m3u(provider.url);
            State.channels = channels.map(ch => ({ ...ch, type: 'live' }));
            State.filteredChannels = [...State.channels];

            // Build groups
            State.m3uGroups = group_channels(State.channels);
            State.m3uGroupList = get_groups(State.channels);

            showToast('Geladen: ' + provider.name + ` (${channels.length} Kanäle)`, 'success');
            renderM3uCategories();
            renderChannels(State.filteredChannels);
        }
    } catch (err) {
        showToast('Fehler beim Laden: ' + err.message, 'error');
        State.activeProvider = null;
        setActiveProviderId(null);
    } finally {
        showLoading(false);
        renderSavedProviders();
    }
}

// ================================================================
//  SAVE PROVIDER — FORM HANDLERS
// ================================================================
function saveXtreamProvider() {
    const name = dom.xtreamName.value.trim();
    const server = dom.xtreamServer.value.trim();
    const user = dom.xtreamUser.value.trim();
    const pass = dom.xtreamPass.value.trim();

    if (!name || !server || !user || !pass) {
        showToast('Bitte alle Felder ausfüllen', 'error');
        return;
    }

    const provider = addProvider({
        type: 'xtream',
        name, server, user, pass
    });

    // Clear form
    dom.xtreamName.value = '';
    dom.xtreamServer.value = '';
    dom.xtreamUser.value = '';
    dom.xtreamPass.value = '';

    renderSavedProviders();
    showToast('Provider gespeichert', 'success');

    // Auto-activate
    activateProvider(provider.id);
}

function saveM3uProvider() {
    const name = dom.m3uName.value.trim();
    const url = dom.m3uUrl.value.trim();

    if (!name || !url) {
        showToast('Bitte Name und URL angeben', 'error');
        return;
    }

    const provider = addProvider({
        type: 'm3u',
        name, url
    });

    // Clear form
    dom.m3uName.value = '';
    dom.m3uUrl.value = '';

    renderSavedProviders();
    showToast('Provider gespeichert', 'success');

    // Auto-activate
    activateProvider(provider.id);
}

// ================================================================
//  D-PAD NAVIGATION
// ================================================================
let focusedElement = null;
let navRegions = ['header', 'sidebar', 'content'];
let currentRegion = 'content';

function initDpadNavigation() {
    document.addEventListener('keydown', handleDpadKeydown);

    // Track focus changes
    document.addEventListener('focusin', (e) => {
        focusedElement = e.target;
        // Determine region
        if (focusedElement.closest('.smt-header')) currentRegion = 'header';
        else if (focusedElement.closest('.smt-sidebar')) currentRegion = 'sidebar';
        else if (focusedElement.closest('.smt-content')) currentRegion = 'content';
        else if (focusedElement.closest('.smt-modal')) currentRegion = 'modal';
    });
}

function handleDpadKeydown(e) {
    // If modal is open, handle modal navigation
    if (dom.providerModal.classList.contains('active')) {
        handleModalDpad(e);
        return;
    }

    // Enter = select/click
    if (e.key === 'Enter') {
        if (focusedElement) {
            e.preventDefault();
            focusedElement.click();
        }
        return;
    }

    // Escape / Back = go back
    if (e.key === 'Escape' || e.key === 'Back' || e.keyCode === 427 || e.keyCode === 461) {
        if (dom.providerModal.classList.contains('active')) {
            e.preventDefault();
            closeProviderModal();
            return;
        }
        // If on player page, go back — handled by Android WebView
        // If search has text, clear it
        if (dom.searchInput && dom.searchInput.value) {
            dom.searchInput.value = '';
            applySearch('');
            e.preventDefault();
            return;
        }
        return;
    }

    // Arrow keys for spatial navigation
    switch (e.key) {
        case 'ArrowUp':
            e.preventDefault();
            navigateUp();
            break;
        case 'ArrowDown':
            e.preventDefault();
            navigateDown();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            navigateLeft();
            break;
        case 'ArrowRight':
            e.preventDefault();
            navigateRight();
            break;
    }
}

function navigateUp() {
    const focusables = getRegionFocusables(currentRegion);
    if (focusables.length === 0) return;

    const currentIdx = focusables.indexOf(focusedElement);
    if (currentIdx === -1) {
        focusables[0].focus();
        return;
    }

    // Try to find element above in the same column
    const currentRect = focusedElement.getBoundingClientRect();
    let bestCandidate = null;
    let bestDistance = Infinity;

    for (let i = 0; i < focusables.length; i++) {
        const el = focusables[i];
        const rect = el.getBoundingClientRect();
        if (rect.top < currentRect.top - 5) {
            const distance = Math.abs(rect.left - currentRect.left) + (currentRect.top - rect.top);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestCandidate = el;
            }
        }
    }

    if (bestCandidate) {
        bestCandidate.focus();
    } else {
        // Switch to header region
        if (currentRegion === 'content' || currentRegion === 'sidebar') {
            currentRegion = 'header';
            const headerFocusables = getRegionFocusables('header');
            if (headerFocusables.length > 0) {
                headerFocusables[0].focus();
            }
        }
    }
}

function navigateDown() {
    const focusables = getRegionFocusables(currentRegion);
    if (focusables.length === 0) return;

    const currentRect = focusedElement ? focusedElement.getBoundingClientRect() : null;
    if (!currentRect) {
        focusables[0].focus();
        return;
    }

    let bestCandidate = null;
    let bestDistance = Infinity;

    for (const el of focusables) {
        const rect = el.getBoundingClientRect();
        if (rect.top > currentRect.top + 5) {
            const distance = Math.abs(rect.left - currentRect.left) + (rect.top - currentRect.top);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestCandidate = el;
            }
        }
    }

    if (bestCandidate) {
        bestCandidate.focus();
    } else if (currentRegion === 'header') {
        // Move to content or sidebar
        currentRegion = 'content';
        const contentFocusables = getRegionFocusables('content');
        if (contentFocusables.length > 0) {
            contentFocusables[0].focus();
        }
    }
}

function navigateLeft() {
    if (currentRegion === 'content') {
        // Move to sidebar
        currentRegion = 'sidebar';
        const sidebarFocusables = getRegionFocusables('sidebar');
        if (sidebarFocusables.length > 0) {
            // Focus the closest item
            sidebarFocusables[0].focus();
        }
        return;
    }

    if (currentRegion === 'sidebar') {
        // Move to header
        currentRegion = 'header';
        const headerFocusables = getRegionFocusables('header');
        if (headerFocusables.length > 0) {
            headerFocusables[headerFocusables.length - 1].focus();
        }
        return;
    }

    // Within region: move to previous item
    const focusables = getRegionFocusables(currentRegion);
    const currentIdx = focusables.indexOf(focusedElement);
    if (currentIdx > 0) {
        focusables[currentIdx - 1].focus();
    }
}

function navigateRight() {
    if (currentRegion === 'header') {
        // Move to sidebar or content
        currentRegion = 'content';
        const contentFocusables = getRegionFocusables('content');
        if (contentFocusables.length > 0) {
            contentFocusables[0].focus();
        }
        return;
    }

    if (currentRegion === 'sidebar') {
        // Move to content
        currentRegion = 'content';
        const contentFocusables = getRegionFocusables('content');
        if (contentFocusables.length > 0) {
            contentFocusables[0].focus();
        }
        return;
    }

    // Within content: move to next item
    const focusables = getRegionFocusables(currentRegion);
    const currentIdx = focusables.indexOf(focusedElement);
    if (currentIdx >= 0 && currentIdx < focusables.length - 1) {
        focusables[currentIdx + 1].focus();
    }
}

function handleModalDpad(e) {
    // Simple tab navigation in modal
    const focusables = getModalFocusables();
    const currentIdx = focusables.indexOf(focusedElement);

    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            if (currentIdx >= 0 && currentIdx < focusables.length - 1) {
                focusables[currentIdx + 1].focus();
            } else if (currentIdx === -1 && focusables.length > 0) {
                focusables[0].focus();
            }
            break;
        case 'ArrowUp':
            e.preventDefault();
            if (currentIdx > 0) {
                focusables[currentIdx - 1].focus();
            }
            break;
        case 'ArrowLeft':
        case 'ArrowRight':
            e.preventDefault();
            // Could handle horizontal navigation in form rows
            break;
    }
}

function getModalFocusables() {
    return Array.from(dom.providerModal.querySelectorAll('button, input, [tabindex="0"]')).filter(
        el => el.offsetParent !== null && !el.disabled && el.style.display !== 'none'
    );
}

function getRegionFocusables(region) {
    let selector;
    switch (region) {
        case 'header':
            selector = '.smt-header button, .smt-header input';
            break;
        case 'sidebar':
            selector = '.smt-sidebar button, .smt-sidebar [tabindex="0"]';
            break;
        case 'content':
            selector = '.smt-content button, .smt-content [tabindex="0"]';
            break;
        default:
            selector = 'button, input, [tabindex="0"]';
    }

    const elements = Array.from(document.querySelectorAll(selector)).filter(
        el => el.offsetParent !== null && !el.disabled
    );

    return elements;
}

// ================================================================
//  INIT — EVENT LISTENERS
// ================================================================
function initEventListeners() {
    // Header buttons
    if (dom.btnProviders) dom.btnProviders.addEventListener('click', openProviderModal);
    if (dom.btnCloseModal) dom.btnCloseModal.addEventListener('click', closeProviderModal);
    if (dom.btnAddProviderEmpty) dom.btnAddProviderEmpty.addEventListener('click', openProviderModal);
    if (dom.btnAddProviderWelcome) dom.btnAddProviderWelcome.addEventListener('click', openProviderModal);

    // Provider modal overlay click to close
    if (dom.providerModal) {
        dom.providerModal.addEventListener('click', (e) => {
            if (e.target === dom.providerModal) closeProviderModal();
        });
    }

    // Provider type tabs
    $$('.smt-provider-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            $$('.smt-provider-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const type = tab.dataset.providerType;
            dom.formXtream.style.display = type === 'xtream' ? 'block' : 'none';
            dom.formM3u.style.display = type === 'm3u' ? 'block' : 'none';
        });
    });

    // Save buttons
    if (dom.btnSaveXtream) dom.btnSaveXtream.addEventListener('click', saveXtreamProvider);
    if (dom.btnSaveM3u) dom.btnSaveM3u.addEventListener('click', saveM3uProvider);

    // Content tabs (Live / VOD / Series)
    $$('.smt-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Search input
    if (dom.searchInput) {
        dom.searchInput.addEventListener('input', (e) => {
            applySearch(e.target.value);
        });
    }
}

// ================================================================
//  AUTO-LOAD LAST PROVIDER
// ================================================================
async function autoLoadLastProvider() {
    const activeId = getActiveProviderId();
    if (activeId) {
        const provider = findProvider(activeId);
        if (provider) {
            await activateProvider(activeId);
            return;
        }
    }

    // If only one provider saved, auto-load it
    if (State.providers.length === 1) {
        await activateProvider(State.providers[0].id);
        return;
    }

    // Otherwise show welcome
    resetContent();
}

// ================================================================
//  APP START
// ================================================================
async function initApp() {
    loadProviders();
    initEventListeners();
    initDpadNavigation();
    renderSavedProviders();

    // Auto-load last provider
    try {
        await autoLoadLastProvider();
    } catch (err) {
        showToast('Auto-Load fehlgeschlagen: ' + err.message, 'error');
    }
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', initApp);

// ================================================================
//  GLOBAL EXPORTS (for onclick handlers in HTML)
// ================================================================
if (typeof window !== 'undefined') {
    window.openProviderModal = openProviderModal;
    window.closeProviderModal = closeProviderModal;
    window.activateProvider = activateProvider;
    window.deleteProvider = deleteProvider;
    window.playChannel = playChannel;
    window.switchTab = switchTab;
}