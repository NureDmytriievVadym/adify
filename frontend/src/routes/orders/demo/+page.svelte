<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import { demoListings, formatUah } from '#lib/demo/marketplace.ts';
  const listing = demoListings[1];
  const stages = [
    {
      title: 'Agree on the placement',
      description: 'Scope and technical requirements confirmed.',
      done: true,
    },
    {
      title: 'Prepare the placement',
      description: 'The provider is working on the agreed placement.',
      done: false,
    },
    {
      title: 'Review the work',
      description: 'The customer reviews the submitted work.',
      done: false,
    },
  ];
</script>

<svelte:head
  ><title>Sample order — Adify</title><meta
    name="description"
    content="Read-only example of an Adify advertising order. Sample stages, placement requirements, and order details."
  /></svelte:head
>

<div class="container page-content">
  <nav class="breadcrumbs" aria-label="Breadcrumb">
    <a href="/orders">Orders preview</a><Icon name="chevron" size={13} /><span aria-current="page"
      >Sample order</span
    >
  </nav>
  <PreviewNotice />
  <div class="order-heading">
    <div>
      <span class="eyebrow">SAMPLE ORDER · DEMO-001</span>
      <h1>A good idea,<br /><span>taking shape.</span></h1>
      <p>Website banner placement with Digital Daily</p>
    </div>
    <span class="order-status"><span class="status-dot"></span> In progress</span>
  </div>
  <div class="order-layout">
    <div>
      <section class="surface-panel">
        <div class="panel-title">
          <h2>Work stages</h2>
          <span class="small-note">Read-only example</span>
        </div>
        <ol class="order-stages">
          {#each stages as stage, i (stage.title)}<li class:done={stage.done}>
              <span class="stage-number"
                >{#if stage.done}<Icon name="check" size={18} />{:else}{String(i + 1).padStart(
                    2,
                    '0',
                  )}{/if}</span
              >
              <div>
                <h3>{stage.title}</h3>
                <p>{stage.description}</p>
              </div>
              <span class="stage-state"
                >{stage.done ? 'Complete' : i === 1 ? 'In progress' : 'Upcoming'}</span
              >
            </li>{/each}
        </ol>
      </section>
      <section class="surface-panel">
        <h2>Placement requirements</h2>
        <p class="muted">Example snapshot recorded when the order was created.</p>
        <dl class="specification-list">
          {#each listing.placement as spec (spec.label)}<div>
              <dt>{spec.label}</dt>
              <dd>{spec.value}</dd>
            </div>{/each}
        </dl>
      </section>
      <section class="surface-panel">
        <h2>Evidence & materials</h2>
        <div class="materials-placeholder">
          <Icon name="article" size={26} />
          <p>
            Files and evidence will appear here.<br /><span class="small-note"
              >Uploads are unavailable in this preview.</span
            >
          </p>
        </div>
      </section>
    </div>
    <aside class="order-sidebar">
      <section class="surface-panel">
        <span class="eyebrow">THE AGREEMENT</span>
        <h2>Order summary</h2>
        <dl class="order-summary">
          <div>
            <dt>Customer</dt>
            <dd>Olena M. <span class="small-note">(sample)</span></dd>
          </div>
          <div>
            <dt>Provider</dt>
            <dd>Digital Daily <span class="small-note">(sample)</span></dd>
          </div>
          <div>
            <dt>Agreed price</dt>
            <dd class="summary-price">{formatUah(3500)}</dd>
          </div>
          <div>
            <dt>Payment status</dt>
            <dd>Charged and held by Adify <span class="small-note">(example)</span></dd>
          </div>
        </dl>
        <a href={`/listings/${listing.slug}`} class="text-link"
          >View sample listing <Icon name="arrow" size={17} /></a
        >
      </section>
      <div class="sidebar-note">
        <Icon name="shield" size={24} />
        <p>
          <strong>A layout preview, with no transaction.</strong><br />No funds are held and no
          order actions are performed.
        </p>
      </div>
      <button type="button" class="button button-outline full-width" disabled
        >Submit work for review</button
      >
      <p class="small-note">Order actions will be added with the order workflow.</p>
    </aside>
  </div>
</div>
