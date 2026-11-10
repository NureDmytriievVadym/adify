<script lang="ts">
  import { tick } from 'svelte';
  import { createOrder, validateOrder, type Order, type OrderInput } from '#lib/orders/api.ts';

  let {
    chatId,
    oncreated,
    oncancel,
  }: { chatId: string; oncreated: (order: Order) => void; oncancel: () => void } = $props();

  let input: OrderInput = $state({ details: '', price: '', deadline: '', stages: [] });
  let message = $state('');
  let saving = $state(false);
  let alert: HTMLParagraphElement | undefined = $state();

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = validateOrder(input) ?? '';
    if (!message) {
      saving = true;
      const result = await createOrder(chatId, input);
      saving = false;
      if (result.ok) return oncreated(result.value);
      message = result.message;
    }
    await tick();
    alert?.focus();
  }
</script>

<form class="order-form" novalidate onsubmit={submit} aria-labelledby="order-form-title">
  <h2 id="order-form-title" class="account-title">Create an order</h2>
  <p class="field-hint">
    The order starts awaiting payment. It keeps a copy of the listing’s technical requirements as
    they are now.
  </p>
  {#if message}
    <p class="form-alert" role="alert" tabindex="-1" bind:this={alert}>{message}</p>
  {/if}
  <div class="form-field">
    <label for="order-details">Order details</label>
    <textarea id="order-details" rows="4" maxlength="2000" bind:value={input.details}></textarea>
  </div>
  <div class="order-form-row">
    <div class="form-field">
      <label for="order-price">Agreed price, UAH</label>
      <input id="order-price" inputmode="decimal" placeholder="3000" bind:value={input.price} />
    </div>
    <div class="form-field">
      <label for="order-deadline">Order deadline (optional)</label>
      <input id="order-deadline" type="date" bind:value={input.deadline} />
    </div>
  </div>
  <fieldset class="order-stages">
    <legend>Work stages (optional)</legend>
    {#each input.stages as stage, index (index)}
      <div class="order-form-row order-stage">
        <div class="form-field">
          <label for={`stage-${index}-title`}>Stage {index + 1}</label>
          <input id={`stage-${index}-title`} maxlength="120" bind:value={stage.title} />
        </div>
        <div class="form-field">
          <label for={`stage-${index}-deadline`}>Stage {index + 1} deadline</label>
          <input id={`stage-${index}-deadline`} type="date" bind:value={stage.deadline} />
        </div>
        <button
          class="link-button"
          type="button"
          onclick={() => input.stages.splice(index, 1)}
          aria-label={`Remove stage ${index + 1}`}>Remove</button
        >
      </div>
    {/each}
    {#if input.stages.length < 10}
      <button
        class="button button-outline button-small"
        type="button"
        onclick={() => input.stages.push({ title: '', deadline: '' })}>Add a stage</button
      >
    {/if}
  </fieldset>
  <div class="order-form-actions">
    <button class="button button-dark" type="submit" disabled={saving}
      >{saving ? 'Creating…' : 'Create order'}</button
    >
    <button class="button button-outline" type="button" onclick={oncancel}>Cancel</button>
  </div>
</form>
