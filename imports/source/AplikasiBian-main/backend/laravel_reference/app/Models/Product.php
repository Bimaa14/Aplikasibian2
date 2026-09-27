<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Product extends Model
{
    protected $fillable = [
        'type', 'sku', 'name', 'brand', 'size', 'stock',
        'cost_price', 'selling_price', 'service_fee',
    ];

    protected $casts = [
        'cost_price' => 'float',
        'selling_price' => 'float',
        'service_fee' => 'float',
        'stock' => 'integer',
    ];

    public function transactionDetails()
    {
        return $this->hasMany(TransactionDetail::class);
    }

    public function isService(): bool
    {
        return $this->type === 'jasa';
    }

    /** Laba per unit: barang = jual - modal, jasa = jual - komisi montir */
    public function unitProfit(): float
    {
        return $this->isService()
            ? $this->selling_price - $this->service_fee
            : $this->selling_price - $this->cost_price;
    }
}
