<script lang="ts">
  import ConfirmDialog, { type Confirmation } from './ConfirmDialog.svelte';
  import Icon from './Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import {
    acceptWork,
    answerChangeRequest,
    formatMoment,
    requestChanges,
    submitForReview,
    type ChangeRequest,
    type Order,
    type OrderResult,
  } from '#lib/orders/api.ts';

  // FR-040–FR-044: submitting work, accepting it, and the change-request rounds. Every step
  // changes the order's state, so each one is confirmed first.
  let { order, onchange }: { order: Order; onchange: (order: Order) => void } = $props();

  let busy = $state(false);
  let error: string | null = $state(null);
  let asking = $state(false);
  let message = $state('');
  let confirmation: Confirmation | null = $state(null);

  const me = $derived(session.account?.id);
  const pending = $derived(order.change_requests.find((r) => r.status === 'pending'));

  const outcome: Record<ChangeRequest['status'], string> = {
    pending: 'Waiting for the provider’s answer',
    agreed: 'The provider agreed to make the changes',
    declined: 'The provider declined',
    withdrawn: 'Closed: the customer accepted the work',
  };

  async function run(action: () => Promise<OrderResult<Order>>) {
    busy = true;
    error = null;
    const next = await action();
    busy = false;
    if (!next.ok) {
      error = next.message;
      return;
    }
    asking = false;
    message = '';
    onchange(next.value);
  }

  function confirmSubmit() {
    confirmation = {
      title: 'Submit the work for review?',
      message:
        'The customer will be asked to accept the work or request changes. The order waits in review until they answer.',
      confirmLabel: 'Submit for review',
      run: () => run(() => submitForReview(order.id)),
    };
  }

  function confirmAccept() {
    confirmation = {
      title: 'Accept the work?',
      message: `The order will be completed and you will not be able to request changes any more.${
        pending ? ' Your change request that the provider has not answered will be closed.' : ''
      }`,
      confirmLabel: 'Accept work',
      run: () => run(() => acceptWork(order.id)),
    };
  }

  function sendRequest(event: SubmitEvent) {
    event.preventDefault();
    if (!message.trim()) {
      error = 'Describe what the provider should change.';
      return;
    }
    error = null;
    confirmation = {
      title: 'Send this change request?',
      message:
        'The provider will be asked to agree or decline. You cannot send another request until they answer.',
      confirmLabel: 'Send request',
      run: () => run(() => requestChanges(order.id, message)),
    };
  }

  function confirmAnswer(request: ChangeRequest, agree: boolean) {
    confirmation = agree
      ? {
          title: 'Agree to make the changes?',
          message:
            'The order goes back in progress. Submit the work again when the changes are done.',
          confirmLabel: 'Agree to make changes',
          run: () => run(() => answerChangeRequest(order.id, request.id, true)),
        }
      : {
          title: 'Decline the change request?',
          message:
            'The order stays in review. The customer can accept the work as it is or ask for changes again.',
          confirmLabel: 'Decline request',
          danger: true,
          run: () => run(() => answerChangeRequest(order.id, request.id, false)),
        };
  }
</script>

{#if order.status === 'in_progress'}
  {#if order.provider.id === me}
    <p class="field-hint">When the work is finished, submit it so the customer can review it.</p>
    {#if error}<p class="form-alert" role="alert">{error}</p>{/if}
    <button type="button" class="button button-dark" disabled={busy} onclick={confirmSubmit}
      >{busy ? 'Submitting…' : 'Submit for review'} <Icon name="arrow" /></button
    >
  {:else}
    <p class="field-hint">
      The provider is working on the order. You can review it once they submit the work.
    </p>
  {/if}
{:else if order.status === 'in_review'}
  {#if order.review_started_at}
    <p class="field-hint">Submitted for review on {formatMoment(order.review_started_at)}.</p>
  {/if}
  {#if order.customer.id === me}
    {#if pending}
      <p class="field-hint" role="status">
        You asked for changes. The provider has not agreed or declined yet; you can still accept the
        work as it is.
      </p>
    {:else}
      <p class="field-hint">
        Accept the work to complete the order, or ask the provider for changes.
      </p>
    {/if}
    {#if error}<p class="form-alert" role="alert">{error}</p>{/if}
    {#if asking}
      <form class="order-form" novalidate onsubmit={sendRequest}>
        <div class="form-field">
          <label for="change-message">What should the provider change?</label>
          <textarea id="change-message" rows="4" maxlength="2000" bind:value={message}></textarea>
        </div>
        <div class="order-form-actions">
          <button class="button button-dark" type="submit" disabled={busy}
            >{busy ? 'Sending…' : 'Send request'}</button
          >
          <button
            class="button button-outline"
            type="button"
            onclick={() => ((asking = false), (error = null))}>Cancel</button
          >
        </div>
      </form>
    {:else}
      <div class="order-form-actions">
        <button type="button" class="button button-dark" disabled={busy} onclick={confirmAccept}
          >Accept work</button
        >
        {#if !pending}
          <button type="button" class="button button-outline" onclick={() => (asking = true)}
            >Request changes</button
          >
        {/if}
      </div>
    {/if}
  {:else if pending}
    <p class="field-hint">The customer asked for changes:</p>
    <blockquote class="change-request-message">{pending.message}</blockquote>
    {#if error}<p class="form-alert" role="alert">{error}</p>{/if}
    <div class="order-form-actions">
      <button
        type="button"
        class="button button-dark"
        disabled={busy}
        onclick={() => confirmAnswer(pending, true)}>Agree to make changes</button
      >
      <button
        type="button"
        class="button button-outline"
        disabled={busy}
        onclick={() => confirmAnswer(pending, false)}>Decline</button
      >
    </div>
  {:else}
    <p class="field-hint">Waiting for the customer to accept the work or ask for changes.</p>
  {/if}
{:else if order.status === 'done'}
  <p class="field-hint" role="status">
    Completed{order.completed_at ? ` on ${formatMoment(order.completed_at)}` : ''}: the customer
    accepted the work.
  </p>
{/if}

{#if order.change_requests.length}
  <h3 class="change-requests-title">Change requests</h3>
  <ol class="order-stage-list">
    {#each order.change_requests as request (request.id)}
      <li>
        <strong class="order-details">{request.message}</strong>
        <span>{formatMoment(request.created_at)} · {outcome[request.status]}</span>
      </li>
    {/each}
  </ol>
{/if}

<ConfirmDialog {confirmation} onclose={() => (confirmation = null)} />
