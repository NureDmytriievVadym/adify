<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
</script>

<svelte:head
  ><title>How it works — Adify</title><meta
    name="description"
    content="Learn how Adify is being built to connect advertising customers and providers, from discovering a placement to reviewing the work."
  /></svelte:head
>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">MEET ADIFY</span>
    <h1>Your idea.<br />Their space.<br /><span>A shared possibility.</span></h1>
    <p>
      Adify is an internet advertising marketplace for Ukraine.<br class="desktop-break" /> Here is the
      experience we are building for customers and providers.
    </p>
  </div>
  <PreviewNotice />
  <div class="audience-grid">
    <section class="audience-card">
      <span class="eyebrow">FOR CUSTOMERS</span>
      <h2>Find a place<br />for your brand.</h2>
      <p>
        Explore advertising offers or publish an ad request describing what you need. Discuss the
        details with a provider and agree on the scope.
      </p>
      <ul class="check-list">
        <li><Icon name="check" size={18} /> Discover six internet advertising categories</li>
        <li><Icon name="check" size={18} /> Agree on clear placement requirements</li>
        <li><Icon name="check" size={18} /> Review the work before completion</li>
      </ul>
    </section>
    <section class="audience-card provider-audience">
      <span class="eyebrow">FOR PROVIDERS</span>
      <h2>Make space<br />for good brands.</h2>
      <p>
        Offer an advertising placement or service with its technical requirements. Connect with
        customers and manage the agreed work in one place.
      </p>
      <ul class="check-list">
        <li><Icon name="check" size={18} /> Present your placement and price in UAH</li>
        <li><Icon name="check" size={18} /> Discuss the idea in Adify chat</li>
        <li><Icon name="check" size={18} /> Share evidence and submit work for review</li>
      </ul>
    </section>
  </div>
  <section class="how-details">
    <h2>A few things worth knowing.</h2>
    <div>
      <h3>One account. One marketplace role.</h3>
      <p>
        Each marketplace account is either a customer or a provider. Email and a Ukrainian phone
        number (+380) must be verified before protected actions.
      </p>
    </div>
    <div>
      <h3>Internet advertising, in six categories.</h3>
      <p>
        Website banners, sponsored articles, social media posts, video integrations, stream ads, and
        in-app mobile ads.
      </p>
    </div>
    <div>
      <h3>Payments in UAH, through Mono.</h3>
      <p>
        The planned payment flow holds funds on the customer’s card, charges them when the provider
        starts work, and keeps the funds with Adify until completion or an applicable refund. The
        default platform fee is 10% of the provider’s payout share.
      </p>
    </div>
    <a href="/listings" class="button button-dark"
      >Explore the marketplace preview <Icon name="arrow" size={18} /></a
    >
  </section>
</div>
