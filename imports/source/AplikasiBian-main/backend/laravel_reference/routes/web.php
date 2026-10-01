<?php

use App\Livewire\Pos\PosPage;
use Illuminate\Support\Facades\Route;

Route::get('/', fn () => redirect('/admin'));

// Halaman kasir POS (Livewire v3 full-page component, responsif seperti SPA)
Route::get('/pos', PosPage::class)
    ->middleware(['auth'])
    ->name('pos');

require __DIR__.'/auth.php';
