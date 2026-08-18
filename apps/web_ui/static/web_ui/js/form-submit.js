document.querySelectorAll("[data-submit-on-enter]").forEach((input) => {
  const form = document.getElementById(input.dataset.submitForm);
  if (!form) return;

  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.isComposing) return;
    event.preventDefault();
    form.requestSubmit();
  });
});
