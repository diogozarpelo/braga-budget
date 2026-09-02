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

const reactivateModal = document.querySelector("#reactivate-modal");
const reactivateComponentName = document.querySelector(
    "#reactivate-component-name"
);
const cancelReactivationButton = document.querySelector(
    "#cancel-reactivation"
);
const confirmReactivationButton = document.querySelector(
    "#confirm-reactivation"
);
const reactivateForms = document.querySelectorAll(".reactivate-form");

let pendingReactivationForm = null;

function closeReactivationModal() {
    if (!reactivateModal) {
        return;
    }

    reactivateModal.hidden = true;
    document.body.classList.remove("modal-open");
    pendingReactivationForm = null;
}

if (
    reactivateModal &&
    reactivateComponentName &&
    cancelReactivationButton &&
    confirmReactivationButton
) {
    reactivateForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();

            pendingReactivationForm = form;
            reactivateComponentName.textContent = form.dataset.componentName;
            reactivateModal.hidden = false;
            document.body.classList.add("modal-open");
            cancelReactivationButton.focus();
        });
    });

    cancelReactivationButton.addEventListener(
        "click",
        closeReactivationModal
    );

    confirmReactivationButton.addEventListener("click", () => {
        if (pendingReactivationForm) {
            pendingReactivationForm.submit();
        }
    });

    reactivateModal.addEventListener("click", (event) => {
        if (event.target === reactivateModal) {
            closeReactivationModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !reactivateModal.hidden) {
            closeReactivationModal();
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
const componentRows = document.querySelector("#component-rows");
const addComponentRow = document.querySelector("#add-component-row");
const componentRowTemplate = document.querySelector("#component-row-template");

function parseComponentMoney(value) {
    if (!value) {
        return 0;
    }

    return Number.parseFloat(
        value.replace(/\./g, "").replace(",", ".")
    ) || 0;
}

function updateComponentRowTotal(row) {
    const quantityInput = row.querySelector('input[name="quantity"]');
    const priceInput = row.querySelector('input[name="unit_price"]');
    const totalOutput = row.querySelector(".component-total");

    if (!quantityInput || !priceInput || !totalOutput) {
        return;
    }

    const quantity = Number.parseFloat(quantityInput.value) || 0;
    const unitPrice = parseComponentMoney(priceInput.value);
    const total = quantity * unitPrice;

    totalOutput.textContent = total.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
    });
}

function setupComponentRow(row) {
    const select = row.querySelector(".component-description");
    const quantityInput = row.querySelector('input[name="quantity"]');
    const priceInput = row.querySelector('input[name="unit_price"]');
    const removeButton = row.querySelector(".remove-component");

    if (select && priceInput) {
        select.addEventListener("change", () => {
            const option = select.options[select.selectedIndex];

            if (option && option.dataset.price) {
                priceInput.value = option.dataset.price.replace(".", ",");
            } else {
                priceInput.value = "";
            }

            updateComponentRowTotal(row);
        });
    }

    if (quantityInput) {
        quantityInput.addEventListener("input", () => {
            updateComponentRowTotal(row);
        });
    }

    if (priceInput) {
        priceInput.addEventListener("input", () => {
            updateComponentRowTotal(row);
        });
    }

    if (removeButton) {
        removeButton.addEventListener("click", () => {
            const rows = componentRows.querySelectorAll(".component-row");

            if (rows.length <= 1) {
                select.value = "";
                quantityInput.value = "1";
                priceInput.value = "";
                updateComponentRowTotal(row);
                return;
            }

            row.remove();
            moveAddButtonToLastRow();
        });
    }

    updateComponentRowTotal(row);
}

function moveAddButtonToLastRow() {
    if (!componentRows || !addComponentRow) {
        return;
    }

    const rows = componentRows.querySelectorAll(".component-row");

    if (!rows.length) {
        return;
    }

    const lastRow = rows[rows.length - 1];
    const actions = lastRow.querySelector(".component-row-actions");

    if (actions) {
        actions.appendChild(addComponentRow);
    }
}

if (componentRows) {
    componentRows
        .querySelectorAll(".component-row")
        .forEach(setupComponentRow);
}

if (addComponentRow && componentRowTemplate && componentRows) {
    addComponentRow.addEventListener("click", () => {
        const fragment = componentRowTemplate.content.cloneNode(true);
        const row = fragment.querySelector(".component-row");

        componentRows.appendChild(fragment);

        if (row) {
            setupComponentRow(row);
        }

        moveAddButtonToLastRow();
    });
}

moveAddButtonToLastRow();


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
    ["saved", "updated", "deactivated", "reactivated"].forEach(
        (parameter) => currentUrl.searchParams.delete(parameter)
    );

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

const issueModal = document.querySelector("#issue-modal");
const issueForm = document.querySelector(".issue-form");
const cancelIssueButton = document.querySelector("#cancel-issue");
const confirmIssueButton = document.querySelector("#confirm-issue");

if (
    issueModal &&
    issueForm &&
    cancelIssueButton &&
    confirmIssueButton
) {
    issueForm.addEventListener("submit", (event) => {
        event.preventDefault();

        issueModal.hidden = false;
        document.body.classList.add("modal-open");
        cancelIssueButton.focus();
    });

    function closeIssueModal() {
        issueModal.hidden = true;
        document.body.classList.remove("modal-open");
    }

    cancelIssueButton.addEventListener("click", closeIssueModal);

    confirmIssueButton.addEventListener("click", () => {
        issueForm.submit();
    });

    issueModal.addEventListener("click", (event) => {
        if (event.target === issueModal) {
            closeIssueModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !issueModal.hidden) {
            closeIssueModal();
        }
    });
}



const deleteDraftModal = document.querySelector("#delete-draft-modal");
const deleteDraftForm = document.querySelector("#delete-draft-form");
const cancelDeleteDraft = document.querySelector("#cancel-delete-draft");

document.querySelectorAll(".remove-draft-button").forEach((button) => {
    button.addEventListener("click", () => {
        if (!deleteDraftModal || !deleteDraftForm) {
            return;
        }

        deleteDraftForm.action = button.dataset.deleteUrl;
        deleteDraftModal.hidden = false;
        document.body.classList.add("modal-open");
    });
});

if (cancelDeleteDraft && deleteDraftModal) {
    cancelDeleteDraft.addEventListener("click", () => {
        deleteDraftModal.hidden = true;
        document.body.classList.remove("modal-open");
    });
}

if (deleteDraftModal) {
    deleteDraftModal.addEventListener("click", (event) => {
        if (event.target === deleteDraftModal) {
            deleteDraftModal.hidden = true;
            document.body.classList.remove("modal-open");
        }
    });
}


const quoteStatusModal = document.querySelector("#quote-status-modal");
const quoteStatusForm = document.querySelector("#quote-status-form");
const cancelQuoteStatus = document.querySelector("#cancel-quote-status");

document.querySelectorAll(".change-status-button").forEach((button) => {
    button.addEventListener("click", () => {
        if (!quoteStatusModal || !quoteStatusForm) {
            return;
        }

        quoteStatusForm.action = button.dataset.statusUrl;
        quoteStatusModal.hidden = false;
        document.body.classList.add("modal-open");
    });
});

if (cancelQuoteStatus && quoteStatusModal) {
    cancelQuoteStatus.addEventListener("click", () => {
        quoteStatusModal.hidden = true;
        document.body.classList.remove("modal-open");
    });
}

if (quoteStatusModal) {
    quoteStatusModal.addEventListener("click", (event) => {
        if (event.target === quoteStatusModal) {
            quoteStatusModal.hidden = true;
            document.body.classList.remove("modal-open");
        }
    });
}


const quoteExportModal = document.querySelector("#quote-export-modal");
const cancelQuoteExport = document.querySelector("#cancel-quote-export");
const exportPdfOption = document.querySelector("#export-pdf-option");
const exportImageOption = document.querySelector("#export-image-option");

document.querySelectorAll(".export-quote-button").forEach((button) => {
    button.addEventListener("click", () => {
        if (!quoteExportModal) {
            return;
        }

        quoteExportModal.dataset.quoteId = button.dataset.quoteId;
        quoteExportModal.dataset.pdfUrl = button.dataset.pdfUrl;
        quoteExportModal.dataset.imageUrl = button.dataset.imageUrl;
        quoteExportModal.hidden = false;
        document.body.classList.add("modal-open");
    });
});

if (exportPdfOption && quoteExportModal) {
    exportPdfOption.addEventListener("click", () => {
        const pdfUrl = quoteExportModal.dataset.pdfUrl;

        if (!pdfUrl) {
            return;
        }

        quoteExportModal.hidden = true;
        document.body.classList.remove("modal-open");
        window.location.href = pdfUrl;
    });
}

if (exportImageOption && quoteExportModal) {
    exportImageOption.addEventListener("click", () => {
        const imageUrl = quoteExportModal.dataset.imageUrl;

        if (!imageUrl) {
            return;
        }

        quoteExportModal.hidden = true;
        document.body.classList.remove("modal-open");
        window.location.href = imageUrl;
    });
}

if (cancelQuoteExport && quoteExportModal) {
    cancelQuoteExport.addEventListener("click", () => {
        quoteExportModal.hidden = true;
        document.body.classList.remove("modal-open");
    });
}

if (quoteExportModal) {
    quoteExportModal.addEventListener("click", (event) => {
        if (event.target === quoteExportModal) {
            quoteExportModal.hidden = true;
            document.body.classList.remove("modal-open");
        }
    });
}
