<script lang="ts">
  import Icon from './Icon.svelte';
  import {
    addStage,
    completeStage,
    formatDay,
    formatMoment,
    reopenStage,
    type Order,
    type OrderResult,
    type Stage,
  } from '#lib/orders/api.ts';

  // FR-037 (ADY-022): either participant can add a stage, mark it done, or reopen it while
  // the order is in progress or in review. Disputed and final orders keep their stages frozen.
  let { order, onchange }: { order: Order; onchange: (order: Order) => void } = $props();

  let title = $state('');
  let deadline = $state('');
  let error: string | null = $state(null);
  let busy = $state(false);

  const editable = $derived(order.status === 'in_progress' || order.status === 'in_review');
  const today = $derived(new Date().toISOString().slice(0, 10));

  async function run(action: () => Promise<OrderResult<Order>>) {
    busy = true;
    error = null;
    const result = await action();
    busy = false;
    if (result.ok) onchange(result.value);
    else error = result.message;
  }

  function stageState(stage: Stage) {
    if (stage.completed_at) {
      return `Complete${stage.completed_at ? ` on ${formatMoment(stage.completed_at)}` : ''}${
        stage.completed_by ? ` by ${stage.completed_by.display_name}` : ''
      }.`;
    }
    if (stage.deadline && stage.deadline < today) return 'Overdue.';
    return stage.deadline ? `Due ${formatDay(stage.deadline)}.` : 'No deadline.';
  }

  async function add(event: SubmitEvent) {
    event.preventDefault();
    error = null;
    if (!title.trim()) {
      error = 'Give the stage a name.';
      return;
    }
    if (deadline && deadline < today) {
      error = 'The stage deadline cannot be in the past.';
      return;
    }
    if (deadline && order.deadline && deadline > order.deadline) {
      error = 'The stage deadline cannot be later than the order deadline.';
      return;
    }
    busy = true;
    const result = await addStage(order.id, title, deadline);
    busy = false;
    if (!result.ok) {
      error = result.message;
      return;
    }
    title = '';
    deadline = '';
    onchange(result.value);
  }
</script>

<h2 class="account-title">Work stages</h2>
{#if order.stages.length === 0}
  <p class="field-hint">No separate stages.</p>
{:else}
  <ol class="order-stage-list">
    {#each order.stages as stage (stage.id)}
      <li class:stage-complete={stage.completed_at}>
        <div class="stage-heading">
          <strong>{stage.title}</strong>
          <span class="stage-state">{stageState(stage)}</span>
        </div>
        {#if editable}
          <div class="stage-actions">
            {#if stage.completed_at}
              <button
                type="button"
                class="text-button"
                disabled={busy}
                onclick={() => run(() => reopenStage(order.id, stage.id))}>Reopen stage</button
              >
            {:else}
              <button
                type="button"
                class="text-button"
                disabled={busy}
                onclick={() => run(() => completeStage(order.id, stage.id))}>Mark complete</button
              >
            {/if}
          </div>
        {/if}
      </li>
    {/each}
  </ol>
{/if}

{#if editable}
  <form class="order-form stage-form" novalidate onsubmit={add}>
    <p class="field-hint">Add a stage with a deadline while the work is active.</p>
    <div class="order-form-row">
      <div class="form-field">
        <label for="new-stage-title">Stage name</label>
        <input id="new-stage-title" maxlength="120" bind:value={title} />
      </div>
      <div class="form-field">
        <label for="new-stage-deadline">Stage deadline (optional)</label>
        <input id="new-stage-deadline" type="date" min={today} bind:value={deadline} />
      </div>
    </div>
    <div class="order-form-actions">
      <button class="button button-outline button-small" type="submit" disabled={busy}
        >{busy ? 'Adding…' : 'Add stage'} <Icon name="arrow" size={16} /></button
      >
    </div>
  </form>
{/if}

{#if error}<p class="form-alert" role="alert">{error}</p>{/if}
