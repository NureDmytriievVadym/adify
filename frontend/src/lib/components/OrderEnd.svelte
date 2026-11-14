<script lang="ts">
  import ConfirmDialog, { type Confirmation } from './ConfirmDialog.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { formatUah } from '#lib/listings/catalog.ts';
  import { cancelOrder, formatMoment, rejectOrder, type Order } from '#lib/orders/api.ts';

  // FR-046, FR-047 (ADY-025, ADY-026): before work starts the customer may cancel and the
  // provider may reject the order; Mono releases any held funds. Ended orders say why.
  let { order, onchange }: { order: Order; onchange: (order: Order) => void } = $props();

  let busy = $state(false);
  let error: string | null = $state(null);
  let confirmation: Confirmation | null = $state(null);

  const me = $derived(session.account?.id);
  const endable = $derived(
    (order.status === 'awaiting_payment' || order.status === 'paid') && !order.work_started_at,
  );
  const held = $derived(order.status === 'paid');
  const price = $derived(formatUah(Number(order.price_uah)));

  async function end(action: typeof cancelOrder) {
    busy = true;
    error = null;
    const next = await action(order.id);
    busy = false;
    if (next.ok) onchange(next.value);
    else error = next.message;
  }

  function confirmCancel() {
    confirmation = {
      title: 'Cancel this order?',
      message: held
        ? `The order will be canceled and Mono will release the held ${price} back to your card. This cannot be undone.`
        : 'The order will be canceled and nothing will be charged. This cannot be undone.',
      confirmLabel: 'Cancel order',
      danger: true,
      run: () => end(cancelOrder),
    };
  }

  function confirmReject() {
    confirmation = {
      title: 'Reject this order?',
      message: held
        ? `The order will be rejected and Mono will release the held ${price} back to the customer. This cannot be undone.`
        : 'The order will be rejected before the customer pays. This cannot be undone.',
      confirmLabel: 'Reject order',
      danger: true,
      run: () => end(rejectOrder),
    };
  }

  // The customer of a paid order sees that their money went back.
  const released = $derived(order.paid_at ? ' Mono released the held funds to the customer.' : '');
  const on = $derived(order.canceled_at ? ` on ${formatMoment(order.canceled_at)}` : '');
</script>

{#if endable && order.customer.id === me}
  <h2 class="account-title">Cancel the order</h2>
  <p class="field-hint">
    You can cancel until the provider starts work{held
      ? '; Mono then releases the held funds back to your card'
      : ''}.
  </p>
  {#if error}<p class="form-alert" role="alert">{error}</p>{/if}
  <button type="button" class="button button-outline" disabled={busy} onclick={confirmCancel}
    >{busy ? 'Canceling…' : 'Cancel order'}</button
  >
{:else if endable && order.provider.id === me}
  <h2 class="account-title">Reject the order</h2>
  <p class="field-hint">
    If you cannot fulfil this order, reject it before you start work{held
      ? '; Mono then releases the held funds back to the customer'
      : ''}.
  </p>
  {#if error}<p class="form-alert" role="alert">{error}</p>{/if}
  <button type="button" class="button button-outline" disabled={busy} onclick={confirmReject}
    >{busy ? 'Rejecting…' : 'Reject order'}</button
  >
{:else if order.status === 'in_progress' && order.customer.id === me}
  <p class="field-hint">
    Work has started, so the order can no longer be canceled. If something goes wrong, you will be
    able to open a dispute.
  </p>
{:else if order.status === 'canceled' || order.status === 'rejected'}
  <h2 class="account-title">{order.status === 'rejected' ? 'Rejected' : 'Canceled'}</h2>
  <p class="field-hint" role="status">
    {#if order.cancel_reason === 'start_timeout'}
      Canceled{on}: the provider did not start work in time. Mono released the held funds to the
      customer.
    {:else if order.cancel_reason === 'provider_rejected'}
      Rejected by the provider{on}.{order.paid_at ? ' Funds released:' : ''}{released}
    {:else}
      Canceled by the customer{on}.{released}
    {/if}
  </p>
{/if}

<ConfirmDialog {confirmation} onclose={() => (confirmation = null)} />
