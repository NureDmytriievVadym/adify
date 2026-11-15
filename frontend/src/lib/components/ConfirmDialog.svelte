<script lang="ts" module>
  // A step that changes an order's state, held until the participant confirms it.
  export interface Confirmation {
    title: string;
    message: string;
    confirmLabel: string;
    // Red confirm button for steps that turn something down.
    danger?: boolean;
    run: () => void;
  }
</script>

<script lang="ts">
  // A modal question in the middle of the screen. Escape, Cancel, or a click beside the
  // dialog closes it without doing anything; focus starts on Cancel, the safe choice.
  let { confirmation, onclose }: { confirmation: Confirmation | null; onclose: () => void } =
    $props();

  const id = $props.id();
  let dialog: HTMLDialogElement | undefined = $state();
  let cancel: HTMLButtonElement | undefined = $state();

  $effect(() => {
    if (!dialog) return;
    if (confirmation && !dialog.open) {
      dialog.showModal();
      cancel?.focus();
    } else if (!confirmation && dialog.open) {
      dialog.close();
    }
  });

  function confirm() {
    const run = confirmation?.run;
    onclose();
    run?.();
  }
</script>

<dialog
  bind:this={dialog}
  class="confirm-dialog"
  aria-labelledby={`${id}-title`}
  aria-describedby={`${id}-message`}
  {onclose}
  onclick={(event) => event.target === dialog && onclose()}
>
  {#if confirmation}
    <h2 id={`${id}-title`}>{confirmation.title}</h2>
    <p id={`${id}-message`}>{confirmation.message}</p>
    <div class="order-form-actions">
      <button
        type="button"
        class="button button-dark"
        class:delete-confirm={confirmation.danger}
        onclick={confirm}>{confirmation.confirmLabel}</button
      >
      <button type="button" class="button button-outline" bind:this={cancel} onclick={onclose}
        >Cancel</button
      >
    </div>
  {/if}
</dialog>
