document.addEventListener('DOMContentLoaded', () => {
    const api = window.CairnmarkApi;
    const setupButtons = [...document.querySelectorAll('[data-provider-setup]')];
    const providerFilterButtons = [
        ...document.querySelectorAll('[data-provider-filter]'),
    ];
    const providerCards = [...document.querySelectorAll('[data-provider-card]')];

    function setProviderFilter(selectedProvider) {
        providerFilterButtons.forEach((button) => {
            const isSelected = selectedProvider === 'all'
                || button.dataset.providerFilter === selectedProvider;
            button.classList.toggle('is-active', isSelected);
            button.setAttribute('aria-pressed', String(isSelected));
        });
        providerCards.forEach((card) => {
            card.hidden = selectedProvider !== 'all'
                && card.dataset.providerCard !== selectedProvider;
        });
    }

    providerFilterButtons.forEach((button) => {
        button.addEventListener('click', () => {
            setProviderFilter(button.dataset.providerFilter);
        });
    });

    function modelId(model) {
        if (typeof model === 'string') {
            return model;
        }
        return model.id || model.name || JSON.stringify(model);
    }

    function modelName(model) {
        if (typeof model === 'string') {
            return model;
        }
        return model.name || model.id || JSON.stringify(model);
    }

    function modelDisplayLabel(model, apiProvider) {
        const name = modelName(model);
        if (apiProvider) {
            return `${name} (API)`;
        }
        const size = typeof model === 'object' && model !== null
            ? model.size_gb
            : null;
        return size === null || size === undefined
            ? name
            : `${name} (${size} GB)`;
    }

    // Modality icons read from locally saved parameter data (llama.cpp only).
    const MODALITY_ICONS = [
        {key: 'vision', glyph: '📷', label: 'Vision input'},
        {key: 'video', glyph: '🎥', label: 'Video input'},
        {key: 'audio', glyph: '🎤', label: 'Audio input'},
    ];

    setupButtons.forEach((setupButton) => {
        const provider = setupButton.dataset.provider;
        const modal = document.getElementById(setupButton.dataset.modalTarget);
        const providerLabel = modal.dataset.providerLabel;
        const singleModel = modal.dataset.singleModel === 'true';
        const apiProvider = modal.dataset.apiProvider === 'true';
        const closeButton = modal.querySelector('.close-modal-button');
        const cancelButton = modal.querySelector('.modal-cancel-button');
        const saveButton = modal.querySelector('.modal-save-button');
        const readModelsButton = modal.querySelector('.read-models-button');
        const modelList = modal.querySelector('.model-list');
        const modelListItems = modal.querySelector('.model-list-items');
        const modelCount = modal.querySelector('.model-count');
        const modelSearch = modal.querySelector('.model-search');
        const modelSearchSummary = modal.querySelector('.model-search-summary');
        const selectAllButton = modal.querySelector('.select-all-button');
        const selectAllText = modal.querySelector('.select-all-text');
        const ipInput = modal.querySelector('.provider-ip');
        const portInput = modal.querySelector('.provider-port');
        const apiKeyInput = modal.querySelector('.provider-api-key');
        const providerCount = setupButton.querySelector('[data-provider-count]');
        const providerModelName = setupButton.querySelector('[data-provider-model-name]');
        const providerProtocol = setupButton.closest('.provider-card')
            .querySelector('[data-provider-protocol]');
        const providerAction = setupButton.closest('.provider-action-bar');
        const providerToggle = providerAction.querySelector('[data-provider-toggle]');
        const providerStatus = providerAction.querySelector('[data-provider-status]');
        const providerTabStatus = document.querySelector(
            `[data-provider-tab="${provider}"] [data-provider-tab-status]`,
        );

        function connectionPayload() {
            if (apiProvider) {
                return {
                    ip: modal.dataset.providerEndpoint,
                    port: '443',
                    api_key: apiKeyInput.value.trim(),
                };
            }
            return {
                ip: ipInput.value.trim(),
                port: portInput.value.trim(),
            };
        }

        function setModalOpen(isOpen) {
            modal.hidden = !isOpen;
            modal.setAttribute('aria-hidden', String(!isOpen));
            document.body.classList.toggle('modal-open', isOpen);
        }

        function updateProviderSummary(models, total, enabled) {
            if (providerCount) {
                providerCount.textContent = `${total}/${enabled}`;
            }
            if (providerModelName) {
                const name = models.length > 0
                    ? modelDisplayLabel(models[0], apiProvider)
                    : 'Setup required';
                providerModelName.textContent = name;
                providerModelName.title = name;
            }
        }

        function applyProviderStatus(status) {
            providerToggle.checked = Boolean(status.enabled);
            providerToggle.disabled = !status.can_enable;
            providerAction.classList.toggle('is-online', Boolean(status.online));
            providerAction.classList.toggle('is-enabled', Boolean(status.enabled));
            providerAction.classList.toggle('is-unconfigured', !status.configured);

            if (!status.configured) {
                providerStatus.textContent = 'Setup required';
            } else if (!status.online) {
                providerStatus.textContent = 'Offline';
            } else {
                providerStatus.textContent = status.enabled ? 'On' : 'Off';
            }
            if (providerTabStatus) {
                providerTabStatus.textContent = status.online
                    ? `online::${status.enabled ? 'on' : 'off'}`
                    : 'offline';
            }

            if (providerCount) {
                providerCount.textContent = `${status.models_count}/${status.enabled_count}`;
            }
            if (providerModelName) {
                const name = status.model_name
                    ? modelDisplayLabel(
                        {name: status.model_name, size_gb: status.size_gb},
                        apiProvider,
                    )
                    : (status.configured ? 'Server offline' : 'Setup required');
                providerModelName.textContent = name;
                providerModelName.title = name;
            }
        }

        async function refreshProviderStatus() {
            providerToggle.disabled = true;
            providerStatus.textContent = 'Checking…';
            try {
                const query = new URLSearchParams({provider});
                const status = await api.request(
                    `/setup_models/provider_status?${query}`,
                );
                applyProviderStatus(status);
            } catch (error) {
                console.error(`Error checking ${providerLabel} status:`, error);
                applyProviderStatus({
                    configured: true,
                    online: false,
                    enabled: false,
                    can_enable: false,
                    models_count: 0,
                    enabled_count: 0,
                    model_name: null,
                    size_gb: null,
                });
            }
        }

        function updateSelectAllLabel() {
            if (!selectAllText) {
                return;
            }
            const toggles = [...modelListItems.querySelectorAll('input[type="checkbox"]')];
            const allEnabled = toggles.length > 0
                && toggles.every((toggle) => toggle.checked);
            selectAllText.textContent = allEnabled ? 'Deselect All' : 'Select All';
        }

        function filterModels() {
            if (!modelSearch) {
                return;
            }
            const query = modelSearch.value.trim().toLocaleLowerCase();
            const rows = [...modelListItems.querySelectorAll('li[data-model-name]')];
            let visibleCount = 0;

            rows.forEach((item) => {
                const matches = item.dataset.modelName.toLocaleLowerCase().includes(query);
                item.hidden = !matches;
                visibleCount += matches ? 1 : 0;
            });

            modelListItems.querySelector('.model-search-empty')?.remove();
            if (query && rows.length > 0 && visibleCount === 0) {
                const emptyItem = document.createElement('li');
                emptyItem.className = 'model-search-empty';
                emptyItem.textContent = `No model names contain “${modelSearch.value.trim()}”.`;
                modelListItems.appendChild(emptyItem);
            }

            modelSearchSummary.textContent = query
                ? `${visibleCount} of ${rows.length} shown`
                : `${rows.length} ${rows.length === 1 ? 'model' : 'models'}`;
        }

        function displayModels(models, sourceLabel) {
            let normalizedModels = Array.isArray(models)
                ? models
                : (models && Array.isArray(models.data) ? models.data : []);
            if (singleModel) {
                normalizedModels = normalizedModels.slice(0, 1);
            }

            modelListItems.replaceChildren();
            normalizedModels.forEach((model) => {
                const id = modelId(model);
                const name = modelName(model);
                const item = document.createElement('li');
                item.dataset.modelName = name;
                item.dataset.modelId = id;
                const size = typeof model === 'object' && model !== null
                    ? model.size_gb
                    : null;
                item.dataset.modelSize = size === null || size === undefined
                    ? ''
                    : String(size);

                const nameShell = document.createElement('span');
                nameShell.className = 'model-name-shell';
                const nameElement = document.createElement('span');
                nameElement.className = 'model-name-text';
                nameElement.textContent = modelDisplayLabel(model, apiProvider);
                nameShell.appendChild(nameElement);

                // Show saved modality icons (llama.cpp only, DB data only).
                if (provider === 'llama.cpp' && model.modalities && typeof model.modalities === 'object') {
                    MODALITY_ICONS.forEach((icon) => {
                        if (model.modalities[icon.key] === true) {
                            const iconElement = document.createElement('span');
                            iconElement.className = 'model-modality-icon';
                            iconElement.textContent = icon.glyph;
                            iconElement.title = icon.label;
                            iconElement.setAttribute('aria-label', icon.label);
                            nameShell.appendChild(iconElement);
                        }
                    });
                }

                item.appendChild(nameShell);
                if (singleModel) {
                    item.classList.add('is-single-model');
                    const activeState = document.createElement('span');
                    activeState.className = 'single-model-state';
                    activeState.textContent = 'Active';
                    item.appendChild(activeState);
                } else {
                    const switchLabel = document.createElement('label');
                    switchLabel.className = 'switch';
                    switchLabel.setAttribute(
                        'aria-label',
                        `Enable ${modelDisplayLabel(model, apiProvider)}`,
                    );

                    const toggle = document.createElement('input');
                    toggle.type = 'checkbox';
                    toggle.checked = typeof model === 'object' && model !== null
                        && typeof model.enabled === 'boolean'
                        ? model.enabled
                        : true;
                    toggle.addEventListener('change', updateSelectAllLabel);

                    const slider = document.createElement('span');
                    slider.className = 'slider';
                    switchLabel.append(toggle, slider);
                    item.appendChild(switchLabel);
                }
                modelListItems.appendChild(item);
            });

            if (normalizedModels.length === 0) {
                const emptyItem = document.createElement('li');
                emptyItem.textContent = `No saved models for ${providerLabel}.`;
                modelListItems.appendChild(emptyItem);
            }

            modelList.hidden = false;
            saveButton.disabled = normalizedModels.length === 0;
            if (modelSearch) {
                modelSearch.disabled = normalizedModels.length === 0;
                modelSearch.value = '';
            }
            const noun = normalizedModels.length === 1 ? 'model' : 'models';
            modelCount.textContent = `${normalizedModels.length} ${noun} · ${sourceLabel}`;
            filterModels();
            updateSelectAllLabel();
            return normalizedModels;
        }

        async function loadSavedConfiguration() {
            modelList.hidden = false;
            modelListItems.innerHTML = '<li>Loading saved models…</li>';
            modelCount.textContent = 'Loading catalog';
            if (modelSearch) {
                modelSearch.disabled = true;
                modelSearch.value = '';
                modelSearchSummary.textContent = 'Loading';
            }
            saveButton.disabled = true;

            try {
                const query = new URLSearchParams({provider});
                const data = await api.request(
                    `/setup_models/load_configuration?${query}`,
                );
                if (ipInput && data.ip) {
                    ipInput.value = data.ip;
                }
                if (portInput && data.port) {
                    portInput.value = data.port;
                }
                if (apiKeyInput) {
                    apiKeyInput.value = '';
                    apiKeyInput.placeholder = data.has_api_key
                        ? 'Saved API key — leave blank to reuse'
                        : 'Enter API key';
                }
                if (singleModel && data.ip && data.port) {
                    await readModelsFromServer(true);
                } else {
                    const models = displayModels(data.models, 'saved');
                    updateProviderSummary(models, data.models_count, data.enabled_count);
                }
            } catch (error) {
                console.error(`Error loading ${providerLabel} configuration:`, error);
                modelListItems.innerHTML = '<li>Saved models could not be loaded.</li>';
            }
        }

        async function readModelsFromServer(silent = false) {
            const connection = connectionPayload();
            if (!connection.ip || !connection.port) {
                alert('Please enter both IP address and port');
                return;
            }

            readModelsButton.disabled = true;
            readModelsButton.innerHTML = '<span aria-hidden="true">↻</span><span><small>Querying endpoint</small><strong>Loading...</strong></span>';

            try {
                const responseData = await api.json('/setup_models/fetch_models', {
                    method: 'POST',
                    body: {provider, ...connection},
                });
                const models = displayModels(
                    responseData.data || responseData,
                    'server',
                );
                if (singleModel) {
                    updateProviderSummary(models, models.length, models.length);
                }
            } catch (error) {
                console.error(`Error fetching ${providerLabel} models:`, error);
                if (!silent) {
                    alert(
                        `Failed to fetch models from ${providerLabel}. `
                        + (apiProvider
                            ? 'Check the key type, permissions, billing, and provider status.\n\n'
                            : `Please ensure it is available at ${connection.ip}:${connection.port}/v1/models.\n\n`)
                        + `Error details: ${error.message}`,
                    );
                }
            } finally {
                readModelsButton.disabled = false;
                const source = apiProvider ? `Query ${providerLabel}` : 'Query local server';
                readModelsButton.innerHTML = `<span aria-hidden="true">↻</span><span><small>${source}</small><strong>Read Models</strong></span>`;
            }
        }

        async function saveConfiguration() {
            const connection = connectionPayload();
            const models = [...modelListItems.querySelectorAll('li[data-model-name]')]
                .map((item) => ({
                    id: item.dataset.modelId || item.dataset.modelName,
                    name: item.dataset.modelId || item.dataset.modelName,
                    size_gb: item.dataset.modelSize
                        ? Number(item.dataset.modelSize)
                        : null,
                    enabled: singleModel
                        ? true
                        : item.querySelector('input[type="checkbox"]').checked,
                }));

            if (!connection.ip || !connection.port) {
                alert('Please enter both IP address and port');
                return;
            }
            if (models.length === 0) {
                alert('There are no models to save');
                return;
            }

            saveButton.disabled = true;
            saveButton.innerHTML = '<span aria-hidden="true">✓</span> Saving...';
            try {
                const result = await api.json('/setup_models/save_configuration', {
                    method: 'POST',
                    body: {provider, models, ...connection},
                });
                updateProviderSummary(models, result.models_count, result.enabled_count);
                if (!apiProvider) {
                    providerProtocol.textContent = `${connection.ip.replace(/\/$/, '')}:${connection.port}`;
                } else {
                    apiKeyInput.value = '';
                    apiKeyInput.placeholder = 'Saved API key — leave blank to reuse';
                }
                setModalOpen(false);
                await refreshProviderStatus();
            } catch (error) {
                console.error(`Error saving ${providerLabel} configuration:`, error);
                alert(`Error saving configuration: ${error.message}`);
            } finally {
                saveButton.disabled = false;
                saveButton.innerHTML = '<span aria-hidden="true">✓</span> Save Configuration';
            }
        }

        setupButton.addEventListener('click', async () => {
            setModalOpen(true);
            await loadSavedConfiguration();
            (apiKeyInput || ipInput).focus();
        });
        closeButton.addEventListener('click', () => setModalOpen(false));
        cancelButton.addEventListener('click', () => setModalOpen(false));
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                setModalOpen(false);
            }
        });
        if (modelSearch) {
            modelSearch.addEventListener('input', filterModels);
        }
        readModelsButton.addEventListener('click', () => readModelsFromServer(false));
        saveButton.addEventListener('click', saveConfiguration);
        providerToggle.addEventListener('change', async () => {
            const requestedState = providerToggle.checked;
            providerToggle.disabled = true;
            try {
                await api.json('/setup_models/provider_state', {
                    method: 'POST',
                    body: {provider, enabled: requestedState},
                });
            } catch (error) {
                console.error(`Error changing ${providerLabel} state:`, error);
                alert(error.message);
            } finally {
                await refreshProviderStatus();
            }
        });

        if (selectAllButton) {
            selectAllButton.addEventListener('click', () => {
                const toggles = [...modelListItems.querySelectorAll('input[type="checkbox"]')];
                const enableAll = !toggles.every((toggle) => toggle.checked);
                toggles.forEach((toggle) => {
                    toggle.checked = enableAll;
                });
                updateSelectAllLabel();
            });
        }

        refreshProviderStatus();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') {
            return;
        }
        document.querySelectorAll('[data-provider-modal][aria-hidden="false"]')
            .forEach((modal) => {
                modal.hidden = true;
                modal.setAttribute('aria-hidden', 'true');
            });
        document.body.classList.remove('modal-open');
    });
});
