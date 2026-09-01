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
