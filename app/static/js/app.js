function formatPhone(value) {
    const digits = value.replace(/\D/g, "").slice(0, 11);

    if (digits.length === 0) {
        return "";
    }

    if (digits.length < 3) {
        return `(${digits}`;
    }

    if (digits.length < 7) {
        return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
    }

    if (digits.length <= 10) {
        return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
    }

    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

const phoneInput = document.querySelector('input[name="phone"]');

if (phoneInput) {
    phoneInput.addEventListener("input", (event) => {
        event.target.value = formatPhone(event.target.value);
    });
}

const deactivateModal = document.querySelector("#deactivate-modal");
const deactivateClientName = document.querySelector("#deactivate-client-name");
const cancelDeactivationButton = document.querySelector("#cancel-deactivation");
const confirmDeactivationButton = document.querySelector("#confirm-deactivation");
const deactivateForms = document.querySelectorAll(".deactivate-form");

let pendingDeactivationForm = null;

function closeDeactivationModal() {
    if (!deactivateModal) {
        return;
    }

    deactivateModal.hidden = true;
    document.body.classList.remove("modal-open");
    pendingDeactivationForm = null;
}

if (
    deactivateModal &&
    deactivateClientName &&
    cancelDeactivationButton &&
    confirmDeactivationButton
) {
    deactivateForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();

            pendingDeactivationForm = form;
            deactivateClientName.textContent = form.dataset.clientName;
            deactivateModal.hidden = false;
            document.body.classList.add("modal-open");
            cancelDeactivationButton.focus();
        });
    });

    cancelDeactivationButton.addEventListener("click", closeDeactivationModal);

    confirmDeactivationButton.addEventListener("click", () => {
        if (pendingDeactivationForm) {
            pendingDeactivationForm.submit();
        }
    });

    deactivateModal.addEventListener("click", (event) => {
        if (event.target === deactivateModal) {
            closeDeactivationModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !deactivateModal.hidden) {
            closeDeactivationModal();
        }
    });
}

const widthInput = document.querySelector('input[name="width_mm"]');
const heightInput = document.querySelector('input[name="height_mm"]');
const exactAreaOutput = document.querySelector("#exact-area-output");

function updateExactArea() {
    if (!widthInput || !heightInput || !exactAreaOutput) {
        return;
    }

    const widthMm = Number(widthInput.value);
    const heightMm = Number(heightInput.value);

    if (widthMm > 0 && heightMm > 0) {
        const areaM2 = (widthMm * heightMm) / 1000000;

        exactAreaOutput.textContent = `${areaM2.toLocaleString("pt-BR", {
            minimumFractionDigits: 4,
            maximumFractionDigits: 4,
        })} m²`;

        return;
    }

    exactAreaOutput.textContent = "0,0000 m²";
}

if (widthInput && heightInput && exactAreaOutput) {
    widthInput.addEventListener("input", updateExactArea);
    heightInput.addEventListener("input", updateExactArea);
    updateExactArea();
}

const removeModal = document.querySelector("#remove-modal");
const removeModalTitle = document.querySelector("#remove-modal-title");
const removeTargetName = document.querySelector("#remove-target-name");
const removeModalMessage = document.querySelector("#remove-modal-message");
const cancelRemovalButton = document.querySelector("#cancel-removal");
const confirmRemovalButton = document.querySelector("#confirm-removal");
const removeForms = document.querySelectorAll(".remove-form");

let pendingRemovalForm = null;

function closeRemovalModal() {
    if (!removeModal) {
        return;
    }

    removeModal.hidden = true;
    document.body.classList.remove("modal-open");
    pendingRemovalForm = null;
}

if (
    removeModal &&
    removeModalTitle &&
    removeTargetName &&
    removeModalMessage &&
    cancelRemovalButton &&
    confirmRemovalButton
) {
    removeForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();

            pendingRemovalForm = form;
            removeModalTitle.textContent = form.dataset.confirmTitle;
            removeTargetName.textContent = form.dataset.confirmName;
            removeModalMessage.textContent = form.dataset.confirmMessage;
            removeModal.hidden = false;
            document.body.classList.add("modal-open");
            cancelRemovalButton.focus();
        });
    });

    cancelRemovalButton.addEventListener("click", closeRemovalModal);

    confirmRemovalButton.addEventListener("click", () => {
        if (pendingRemovalForm) {
            pendingRemovalForm.submit();
        }
    });

    removeModal.addEventListener("click", (event) => {
        if (event.target === removeModal) {
            closeRemovalModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !removeModal.hidden) {
            closeRemovalModal();
        }
    });
}

const componentForm = document.querySelector("#component-form");
const componentCategory = componentForm?.querySelector(
    'select[name="category"]'
);
const componentDescription = componentForm?.querySelector(
    'input[name="description"]'
);
const componentQuantity = componentForm?.querySelector(
    'input[name="quantity"]'
);
const kitSuggestion = document.querySelector("#kit-suggestion");
const kitSuggestionText = document.querySelector("#kit-suggestion-text");

let lastSuggestedKitDescription = "";

function updateKitSuggestion(prefillFields) {
    if (
        !componentForm ||
        !componentCategory ||
        !componentDescription ||
        !componentQuantity ||
        !kitSuggestion ||
        !kitSuggestionText
    ) {
        return;
    }

    if (componentCategory.value !== "kit") {
        kitSuggestion.hidden = true;
        return;
    }

    const widthMm = Number(componentForm.dataset.itemWidthMm);
    const itemQuantity = Number(componentForm.dataset.itemQuantity);
    const roundedWidthMm = Math.ceil(widthMm / 500) * 500;
    const kitLengthMeters = roundedWidthMm / 1000;
    const formattedLength = kitLengthMeters.toLocaleString("pt-BR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 1,
    });

    const suggestedDescription = `Kit de instalação ${formattedLength} m`;

    kitSuggestionText.textContent =
        `${suggestedDescription}.`;

    kitSuggestion.hidden = false;

    if (prefillFields) {
        if (
            !componentDescription.value.trim() ||
            componentDescription.value === lastSuggestedKitDescription
        ) {
            componentDescription.value = suggestedDescription;
        }

        componentQuantity.value = itemQuantity;
    }

    lastSuggestedKitDescription = suggestedDescription;
}

if (componentCategory) {
    componentCategory.addEventListener("change", () => {
        updateKitSuggestion(true);
    });

    updateKitSuggestion(false);
}



function formatCnpj(value) {
    const digits = value.replace(/\D/g, "").slice(0, 14);

    if (digits.length <= 2) {
        return digits;
    }

    if (digits.length <= 5) {
        return `${digits.slice(0, 2)}.${digits.slice(2)}`;
    }

    if (digits.length <= 8) {
        return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
    }

    if (digits.length <= 12) {
        return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
    }

    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

const cnpjInput = document.querySelector('input[name="cnpj"]');

if (cnpjInput) {
    cnpjInput.addEventListener("input", (event) => {
        event.target.value = formatCnpj(event.target.value);
    });
}


const settingsSaveToast = document.querySelector(".save-toast");

if (settingsSaveToast) {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("saved");

    window.history.replaceState(
        null,
        "",
        `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`
    );

    window.setTimeout(() => {
        settingsSaveToast.classList.add("is-hiding");

        window.setTimeout(() => {
            settingsSaveToast.remove();
        }, 250);
    }, 2000);
}
